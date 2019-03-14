#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
负责打包的具体任务
security find-identity -p codesigning -v
"""
import base64
import glob
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from logging.handlers import TimedRotatingFileHandler
from subprocess import call, Popen

__DEBUG = os.environ.get("DEBUG", "FALSE").upper() == "TRUE"

logger = logging.getLogger("default")


class Block:
    """
    只是一个语句块的标记而已
    """

    def __init__(self, title, expr=True, log=False, log_both=False, log_cost=False, pass_log=False,
                 fail=True, params=None):
        """
        :param title: 语句块的描述
        :param expr: 额外的表达式
        :param log: 结束时打log
        :param log_both: 开始结束时都打log
        :param log_cost: 记录耗时
        :param pass_log: 表达式为False时打log
        :param fail:
        :param params: 方便输出log的时候附加一些相关参数
        """
        assert isinstance(title, str), "Block的第一个参数是文案"
        self.title = title
        self.log = log or log_both
        self.fail = fail
        self.expr = expr
        self.log_both = log_both
        self.log_cost = log_cost
        self.start = now() if log_cost else 0
        self.params = params
        self.__pass = False  # 是否跳过当前块

    def __enter__(self):
        if self.expr is None or self.expr is False:
            self.__pass = True
        if self.log_both:
            if self.__pass:
                Log("Block[%s] False 开始" % self.title)
            else:
                if self.log:
                    Log("Block[%s] 开始" % self.title)
        return self.expr

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__pass:
            if self.log_cost:
                Log("Block[%s] False 结束 [cost:%s]" % (self.title, (now() - self.start) / 1000))
            else:
                Log("Block[%s] False 结束" % self.title)
        else:
            if self.log:
                if self.log_cost:
                    Log("Block[%s] 结束 [cost:%s]" % (self.title, (now() - self.start) / 1000))
                else:
                    Log("Block[%s] 结束" % self.title)
        if exc_type:
            # 出现异常了
            if self.fail:
                raise exc_type
            else:
                Trace("Block[%s] 出错了" % self.title, exc_type)

        return not self.fail


def makedirs(name, mode=0o777, exist_ok=False):
    head, tail = os.path.split(name)
    if not tail:
        head, tail = os.path.split(head)
    if head and tail and not os.path.exists(head):
        try:
            makedirs(head, exist_ok=exist_ok)
        except FileExistsError:
            # Defeats race condition when another thread created the path
            pass
        cdir = os.curdir
        if isinstance(tail, bytes):
            cdir = bytes(os.curdir)
        if tail == cdir:  # xxx/newdir/. exists if xxx/newdir exists
            return
    try:
        os.mkdir(name, mode)
    except OSError:
        # Cannot rely on checking for EEXIST, since the operating system
        # could give priority to other errors like EACCES or EROFS
        if not exist_ok or not os.path.isdir(name):
            raise


class SmartRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, name):
        TimedRotatingFileHandler.__init__(self, SmartRotatingFileHandler.get_file_name(name),
                                          when='M',
                                          backupCount=30)
        self.__name = name

    @classmethod
    def get_file_name(cls, name):
        return os.path.join(os.environ.get("LOG_PATH", "logs"), "%s.Log.%s" % (name, time.strftime("%Y-%m-%d")))

    def rotate(self, source, dest):
        pass

    # def doRollover(self):
    #     self.baseFilename = SmartRotatingFileHandler.get_file_name(self.__name)
    #     TimedRotatingFileHandler.doRollover(self)


def __init_log():
    log_path = os.environ.get("LOG_PATH", "logs")
    makedirs(log_path, exist_ok=True)
    simple_formatter = logging.Formatter('%(message)s')
    console_formatter = logging.Formatter('%(message)s')
    server_file_handler = SmartRotatingFileHandler("server")
    server_file_handler.setLevel(logging.DEBUG if __DEBUG else logging.INFO)
    server_file_handler.setFormatter(simple_formatter)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if __DEBUG else logging.INFO)
    console_handler.setFormatter(console_formatter)
    logging.getLogger("default").setLevel(logging.INFO)
    logging.getLogger("default").addHandler(server_file_handler)
    if __DEBUG:
        logging.getLogger("default").setLevel(logging.DEBUG)
        logging.getLogger("default").addHandler(console_handler)


__init_log()
_certs = {

}

CODESIGN_BIN = '/usr/bin/codesign'
PLIST_BUDDY_BIN = '/usr/libexec/PlistBuddy'
SECURITY_BIN = '/usr/bin/security'
ZIP_BIN = '/usr/bin/zip'
UNZIP_BIN = '/usr/bin/unzip'


class ReceivedApp(object):
    def __init__(self, path):
        self.path = path

    def unpack_to_dir(self, unpack_dir):
        app_name = os.path.basename(self.path)
        target_dir = os.path.join(unpack_dir, app_name)
        shutil.copytree(self.path, target_dir)
        return App(target_dir)


class ReceivedIpaApp(ReceivedApp):
    def unpack_to_dir(self, target_dir):
        call([UNZIP_BIN, "-qu", self.path, "-d", target_dir])
        return IpaApp(target_dir)


class App(object):
    def __init__(self, path):
        self.path = path
        self.entitlements_path = os.path.join(self.path, 'Entitlements.plist')
        self.app_dir = self.get_app_dir()
        self.provision_path = os.path.join(self.app_dir, 'embedded.mobileprovision')

    def get_app_dir(self):
        return self.path

    def provision(self, provision_path):
        Log("provision_path: {0}".format(provision_path))
        shutil.copyfile(provision_path, self.provision_path)

    def create_entitlements(self):
        # we decode part of the provision path, then extract the
        # Entitlements part, then write that to a file in the app.

        # piping to Plistbuddy doesn't seem to work :(
        # hence, temporary intermediate file

        decoded_provision_fh, decoded_provision_path = tempfile.mkstemp()
        decoded_provision_fh = open(decoded_provision_path, 'w')
        decode_args = [SECURITY_BIN, 'cms', '-D', '-i', self.provision_path]
        process = Popen(decode_args, stdout=decoded_provision_fh)
        # if we don't wait for this to complete, it's likely
        # the next part will see a zero-length file
        process.wait()

        get_entitlements_cmd = [
            PLIST_BUDDY_BIN,
            '-x',
            '-c',
            'print :Entitlements ',
            decoded_provision_path]
        entitlements_fh = open(self.entitlements_path, 'w')
        process2 = Popen(get_entitlements_cmd, stdout=entitlements_fh)
        process2.wait()
        entitlements_fh.close()

        # should destroy the file
        decoded_provision_fh.close()

    # noinspection PyDefaultArgument,PyMethodMayBeStatic
    def codesign(self, certificate, path, extra_args=[]):
        call([CODESIGN_BIN, '-f', '-s', certificate] + extra_args + [path])

    def sign(self, certificate):
        # first sign all the dylibs
        frameworks_path = os.path.join(self.app_dir, 'Frameworks')
        if os.path.exists(frameworks_path):
            dylibs = glob.glob(os.path.join(frameworks_path, '*.dylib'))
            for dylib in dylibs:
                self.codesign(certificate, dylib)
        # then sign the app
        self.codesign(certificate,
                      self.app_dir,
                      ['--entitlements', self.entitlements_path])

    def package(self, output_path):
        if not output_path.endswith('.app'):
            output_path = output_path + '.app'
        os.rename(self.app_dir, output_path)
        return output_path


class IpaApp(App):
    def _get_payload_dir(self):
        return os.path.join(self.path, "Payload")

    def get_app_dir(self):
        glob_path = os.path.join(self._get_payload_dir(), '*.app')
        apps = glob.glob(glob_path)
        count = len(apps)
        if count != 1:
            err = "Expected 1 app in {0}, found {1}".format(glob_path, count)
            raise Exception(err)
        return apps[0]

    def package(self, output_path):
        if not output_path.endswith('.ipa'):
            output_path = output_path + '.ipa'
        Popen([ZIP_BIN, "-qr", os.path.relpath(output_path, self.path), "Payload"], cwd=self.path)
        assert os.path.isfile(output_path), 'zip打包失败'
        return output_path


def absolute_path_argument(path):
    return os.path.abspath(path)


def exists_absolute_path_argument(path):
    return absolute_path_argument(path)


def _redis(host, port, index=13):
    import redis

    if host is None:
        return None
    db = redis.StrictRedis(host=host, port=port, decode_responses=True, db=index)
    db.execute_command("select", "%s" % index)
    return db


# noinspection PyUnresolvedReferences,SpellCheckingInspection
def byteify(src, encoding='utf-8'):
    if isinstance(src, dict):
        return {byteify(key): byteify(value) for key, value in src.iteritems()}
    elif isinstance(src, list):
        return [byteify(element) for element in src]
    elif isinstance(src, eval('unicode')):
        return src.encode(encoding)
    else:
        return src


def _from_topic(topic, is_json=False, limit=10):
    while limit >= 0:
        msg = topic.get_message()
        if msg is None:
            break
        if msg["type"] != "message":
            # 可能是刚刚连上
            continue
        if is_json:
            yield byteify(json.loads(msg["data"], encoding='utf8'))
        else:
            yield msg["data"]


def app_argument(path):
    path = exists_absolute_path_argument(path)
    _, extension = os.path.splitext(path)
    if extension == '.app':
        app = ReceivedApp(path)
    elif extension == '.ipa':
        app = ReceivedIpaApp(path)
    else:
        raise Exception("{0} doesn't seem to be an .app or .ipa".format(path))
    return app


def _package(ipa_file, provisioning_profile, certificate, output_path):
    app = app_argument(ipa_file).unpack_to_dir(os.path.dirname(output_path))
    app.provision(provisioning_profile)
    app.create_entitlements()
    app.sign(certificate)
    app.package(output_path)


def _read_file(path):
    with open(path, mode="rb") as fin:
        return fin.read()


def _write_file(path, content):
    with open(path, mode="wb") as fout:
        fout.write(content)


def md5(content):
    return hashlib.md5(content).hexdigest()


def now():
    """
    ms
    """
    return int(time.time() * 1000)


def Log(msg, first=None, prefix=None, show_ts=True, _logger=None):
    if not show_ts and first is None and prefix is None:
        out = msg
    else:
        ts = time.strftime("%H:%M:%S")
        ts += ".%03d" % (now() % 1000)
        if prefix is not None:
            if first is None:
                first = prefix
            first = "[%s] %s" % (ts, first)
            prefix = "[%s] %s" % (ts, prefix)
            lines = msg.splitlines()
            lines = [first + lines[0]] + list(map(lambda x: prefix + x, lines[1:]))
            out = "\n".join(lines)
        else:
            out = "[%s] %s" % (ts, msg)
    if _logger is None:
        _logger = logger
    _logger.info(out)


def Trace(msg, e, raise_e=False):
    if e is None:
        Log(("%s\n" % msg) + "".join(traceback.format_stack()), first="[TRACE] + ", prefix="[TRACE] - ")
    else:
        exc_type, exc_value, exc_tb = sys.exc_info()
        trace_info = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        out = '''\
%s %s
%s\
''' % (msg, e, trace_info.strip())
        Log(out, first="[TRACE] + ", prefix="[TRACE] - ")
        if raise_e:
            raise e


def _task(cert, cert_p12, mp_url, mp_md5, project, ipa_url, ipa_md5, ipa_new, upload_url):
    base = tempfile.gettempdir()
    # 确认ipa
    if cert not in _certs:
        Log("导入p12")
        _write_file(os.path.join(base, "cert.p12"), base64.decodebytes(cert_p12))

    with Block("mobileprovision部分"):
        file_mp = os.path.join(base, "package.mobileprovision")
        if os.path.isfile(file_mp) and md5(_read_file(file_mp)) == mp_md5:
            Log("采用本地的mobileprovision文件")
        else:
            Log("下载mobileprovision文件")
            makedirs(os.path.join("package", project), exist_ok=True)
            assert call(["wget", mp_url, "-O", file_mp, "-o", "/dev/null"]) == 0, "下载[%s]失败了" % mp_url
            assert md5(_read_file(file_mp)) == mp_md5, "下载[%s]失败" % mp_url
    with Block("ipa部分"):
        file_ipa = os.path.join("package", project, "orig.ipa")
        if os.path.isfile(file_ipa) and md5(_read_file(file_ipa)) == ipa_md5:
            Log("采用本地的ipa文件")
        else:
            Log("下载ipa文件")
            makedirs(os.path.join("package", project), exist_ok=True)
            assert call(["wget", ipa_url, "-O", file_ipa, "-o", "/dev/null"]) == 0, "下载[%s]失败了" % ipa_url
            assert md5(_read_file(file_ipa)) == ipa_md5, "下载[%s]失败了" % ipa_url

    with Block("打包"):
        Log("开始打包[%s]" % project)
        file_new = os.path.join("package", project, ipa_new)
        _package(file_ipa, file_mp, cert, file_new)

    with Block("上传"):
        Log("上传ipa[%s][%s]" % (project, upload_url))
        import requests
        rsp = requests.post(upload_url, files={
            "file": _read_file(file_new),
        })
        assert rsp.status_code == 200
        assert rsp.json()["ret"] == 0
    Log("任务完成")


# noinspection PyBroadException
def run(host, port):
    __pub = _redis(host, port).pubsub()
    __pub.subscribe("task:package")
    last = time.time()

    Log("获取本地签名列表")
    p = Popen("security find-identity -p codesigning -v", bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    expire = time.time() + 30
    while p.poll() is None:
        if time.time() < expire:
            time.sleep(1)
    expr = re.compile(r'\s*\d+\)\s*\S+\s+"([^"]+(\s+\(.+\)))"')
    for each in map(str.strip, p.stdout.readlines()):
        result = expr.match(each)
        if not result:
            continue
        if "REVOKED" in each:
            Log("过期的证书[%s]" % each)
            continue
        try:
            cert, _id = result.groups()
            _certs[cert] = _id.strip()[1:-2]
            _certs[cert[:-len(_id)]] = _id.strip()[1:-2]
            Log("有效的证书[%s]" % each)
        except Exception:
            Log("跳过[%s]" % each)
    Log("等待打包任务")
    while True:
        time.sleep(0.1)
        no_task = True
        for each in _from_topic(__pub, True):
            no_task = False
            try:
                Log("收到任务[%(project)s][%(cert)s]" % each)
                # todo: 任务合并
                # import gevent
                # gevent.spawn(_task, each)
                _task(
                    each["cert"],
                    each["cert_p12"],
                    each["mp_url"],
                    each["mp_md5"],
                    each["project"],
                    each["ipa_url"],
                    each["ipa_md5"],
                    each["ipa_new"],
                    each["upload_url"],
                )
            except Exception as e:
                Trace("出现异常[%s]" % each, e)
        if no_task:
            if time.time() - last > 10:
                last = time.time()
                Log("没有任务")


# noinspection PyProtectedMember,PyPackageRequirements,PyBroadException
def __init_module(module):
    try:
        exec("import %s" % module)
    except Exception:
        import pip._internal
        pip._internal.main(["install", module])


def init_env():
    assert sys.platform == "darwin", "只能运行在mac下"
    # 确认各个核心的命令存在
    for each in filter(lambda x: x.endswith("_BIN"), globals()):
        each = eval(each)
        assert os.path.isfile(each), "请确保文件存在[%s]" % each
    __init_module("redis")
    __init_module("gevent")
    __init_module("requests")


if __name__ == "__main__":
    # 安装基础环境
    init_env()
    if len(sys.argv) >= 2:
        # from gevent import monkey
        #
        # monkey.patch_all()
        run(sys.argv[1], int(sys.argv[2]))
        # _package("/Users/zhangmingluo/Downloads/tmp/test/2048.ipa", "/Users/zhangmingluo/Downloads/tmp/test/_package.mobileprovision",
        #          "iPhone Developer: zhangming luo (ZL8XHT7944)")
    else:
        Log("""\
Usage: 
    sudo python ci_worker.py <redis_host> <redis_port> 
""")
