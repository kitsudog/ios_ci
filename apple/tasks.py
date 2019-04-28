import glob
import os
import re
import shutil
import subprocess
import tempfile
import time
from subprocess import call, Popen

import gevent
import requests
from celery import Task
from celery.task import task

from base.style import Log, Block, now, json_str, Fail
from base.utils import read_binary_file, md5bytes


@task
def print_hello():
    return 'hello celery and django...'


CODESIGN_BIN = '/usr/bin/codesign'
PLIST_BUDDY_BIN = '/usr/libexec/PlistBuddy'
SECURITY_BIN = '/usr/bin/security'
ZIP_BIN = '/usr/bin/zip'
UNZIP_BIN = '/usr/bin/unzip'
_certs = {

}


def _write_file(path, content):
    with open(path, mode="wb") as fout:
        fout.write(content)


class App(object):
    def __init__(self, path):
        self.path = path
        self.entitlements_path = os.path.join(self.path, 'Entitlements.plist')
        self.app_dir = self.get_app_dir()
        self.provision_path = os.path.join(self.app_dir, 'embedded.mobileprovision')

    def get_app_dir(self):
        return self.path

    def provision(self, provision_path):
        Log("provision_path[{0}]".format(provision_path))
        shutil.copyfile(provision_path, self.provision_path)

    def create_entitlements(self):
        # we decode part of the provision path, then extract the
        # Entitlements part, then write that to a file in the app.

        # piping to Plistbuddy doesn't seem to work :(
        # hence, temporary intermediate file

        decoded_provision_fh, decoded_provision_path = tempfile.mkstemp()
        with open(decoded_provision_path, 'w') as decoded_provision_fh:
            decode_args = [SECURITY_BIN, 'cms', '-D', '-i', self.provision_path]
            process = Popen(decode_args, stdout=decoded_provision_fh)
            # if we don't wait for this to complete, it's likely
            # the next part will see a zero-length file
            process.wait()
            assert process.returncode == 0, "decode a CMS message error"

            get_entitlements_cmd = [
                PLIST_BUDDY_BIN,
                '-x',
                '-c',
                'print :Entitlements ',
                decoded_provision_path]
            with open(self.entitlements_path, 'w') as entitlements_fh:
                process2 = Popen(get_entitlements_cmd, stdout=entitlements_fh)
                process2.wait()
                assert process2.returncode == 0, "创建Entitlements.plist失败"

    # noinspection PyDefaultArgument,PyMethodMayBeStatic
    def codesign(self, certificate, path, extra_args=[]):
        _run(" ".join([CODESIGN_BIN, '-f', '-s', certificate] + extra_args + [path]), succ_only=True, debug=True)

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
        _run(" ".join([ZIP_BIN, "-qr", os.path.relpath(output_path, self.path), "Payload"]), pwd=self.path, succ_only=True)
        assert os.path.isfile(output_path), 'zip打包失败'
        return output_path


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


def absolute_path_argument(path):
    return os.path.abspath(path)


def exists_absolute_path_argument(path):
    return absolute_path_argument(path)


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
    Log("准备provision")
    app.provision(provisioning_profile)
    Log("构造entitlements")
    app.create_entitlements()
    Log("签名证书")
    app.sign(certificate)
    Log("重新封包")
    app.package(output_path)


@task
def refresh_certs():
    _refresh_certs()


def _run(cmd: str, timeout=30000, succ_only=False, include_err=True, err_last=False, pwd=None, verbose=False, debug=False):
    if debug:
        verbose = True
    if verbose:
        if debug:
            Log("+ [%s] [%s]" % (pwd or os.path.curdir, cmd))
        else:
            Log("+ [%s]" % cmd)
    p = Popen(cmd, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT if include_err and not err_last else subprocess.PIPE,
              shell=True, cwd=pwd)
    expire = now() + timeout
    buffer = []
    buffer_err = []
    while p.poll() is None:
        if now() < expire:
            time.sleep(0.1)
        else:
            p.kill()
            break
        if p.stdout.readable():
            buffer.extend(p.stdout.readlines())
        if include_err:
            if err_last:
                if p.stderr.readable():
                    buffer_err.extend(p.stderr.readlines())

    if succ_only:
        if p.returncode == 0:
            pass
        else:
            raise Fail("命令[%s]执行失败" % cmd)
    if p.stdout and p.stdout.readable():
        buffer.extend(p.stdout.readlines())
    if p.stderr and p.stderr.readable():
        buffer_err.extend(p.stderr.readlines())
    if debug:
        for each in map(lambda x: x.decode("utf8"), buffer):  # type:str
            Log("- %s" % each.rstrip("\r\n"))
            yield each.rstrip("\r\n")
        if err_last:
            for each in map(lambda x: x.decode("utf8"), buffer_err):  # type:str
                Log("* %s" % each.rstrip("\r\n"))
                yield each.rstrip("\r\n")
    else:
        for each in map(lambda x: x.decode("utf8"), buffer):  # type:str
            yield each.rstrip("\r\n")
        if err_last:
            for each in map(lambda x: x.decode("utf8"), buffer_err):  # type:str
                yield each.rstrip("\r\n")


# noinspection SpellCheckingInspection
def _load_awwdrca():
    """
    加载 Apple Worldwide Developer Relations Certification Authority
    """
    for each in _run("security find-certificate -a", succ_only=True):
        if "Apple Worldwide Developer Relations Certification Authority" in each:
            return True
    Log("加载AppleWWDRCA")
    base = tempfile.gettempdir()
    _run("curl -sSLk https://developer.apple.com/certificationauthority/AppleWWDRCA.cer -o %s/AppleWWDRCA.cer" % base)
    _run("security add-certificates %s/AppleWWDRCA.cer" % base)
    return True


def _check_cert(cert: str, fail=False) -> bool:
    _load_awwdrca()
    _refresh_certs()
    if cert in _certs:
        return True
    if fail:
        raise Fail("找不到指定的证书")
    return False


def _refresh_certs():
    p = Popen("security find-identity -p codesigning -v", bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    expire = now() + 30000
    while p.poll() is None:
        if now() < expire:
            gevent.sleep(1)
    expr = re.compile(r'\s*\d+\)\s*\S+\s+"([^"]+(\s+\(.+\)))"')
    for each in map(lambda x: x.decode("utf8").strip(), p.stdout.readlines()):
        result = expr.match(each)
        if not result:
            continue
        if "REVOKED" in each:
            Log("过期的证书[%s]" % each)
            continue
        # noinspection PyBroadException
        try:
            cert, _id = result.groups()
            _certs[cert] = _id.strip()[1:-2]
            _certs[cert[:-len(_id)]] = _id.strip()[1:-2]
            Log("有效的证书[%s]" % each)
        except:
            Log("跳过[%s]" % each)


def _update_state(url: str, worker: str, state: str, fail=False):
    try:
        requests.post(url, data={
            "worker": worker,
            "state": state
        }, timeout=3)
    except Exception as e:
        if fail:
            if fail is True:
                raise e
            else:
                raise Exception(fail)


def _download(url, file, md5=None):
    # assert call(["wget", url, "-O", file, "-o", "/dev/null"]) == 0, "下载[%s]失败了" % url
    assert call(["curl", url, "-o", file, "-sSLk"]) == 0, "下载[%s]失败了" % url
    if md5:
        assert md5bytes(read_binary_file(file)) == md5, "下载[%s]校验失败" % url


# noinspection PyBroadException
@task(bind=True, time_limit=120, max_retries=3, default_retry_delay=10)
def resign_ipa(self: Task, uuid: str, cert: str, cert_url: str, cert_md5: str, mp_url, mp_md5, project, ipa_url, ipa_md5, ipa_new,
               upload_url, process_url: str):
    worker = self.request.hostname
    Log("[%s]启动Celery任务[%s][%s][%s]" % (worker, uuid, self.request.retries, json_str(self.request.kwargs)))
    base = tempfile.gettempdir()
    _update_state(process_url, worker, "ready")
    try:
        # 确认ipa
        with Block("cert部分"):
            if cert in _certs:
                Log("钥匙串中已经拥有证书[%s]" % cert)
            else:
                _refresh_certs()
            if cert in _certs:
                Log("钥匙串中已经拥有证书[%s]" % cert)
            else:
                _update_state(process_url, worker, "prepare_cert")
                Log("下载证书p12[%s]" % cert)
                file_cert = os.path.join(base, "cert.p12")
                _download(cert_url, file_cert, md5=cert_md5)
                Log("导入证书p12[%s]" % cert)
                assert call([SECURITY_BIN, "import", file_cert, "-P", "q1w2e3r4"]) == 0, "导入证书[%s]失败" % cert
                if not _check_cert(cert):
                    _update_state(process_url, worker, "exception", fail=True)
        with Block("mobileprovision部分"):
            file_mp = os.path.join(base, "package.mobileprovision")
            if os.path.isfile(file_mp) and md5bytes(read_binary_file(file_mp)) == mp_md5:
                Log("采用本地的mobileprovision文件")
            else:
                _update_state(process_url, worker, "prepare_mp")
                Log("下载mobileprovision文件")
                os.makedirs(os.path.join("package", project), exist_ok=True)
                _download(mp_url, file_mp, md5=mp_md5)
        with Block("ipa部分"):
            file_ipa = os.path.join("package", project, "orig.ipa")
            if os.path.isfile(file_ipa) and md5bytes(read_binary_file(file_ipa)) == ipa_md5:
                Log("采用本地的ipa文件")
            else:
                _update_state(process_url, worker, "prepare_ipa")
                Log("下载ipa文件[%s]" % ipa_url)
                os.makedirs(os.path.join("package", project), exist_ok=True)
                _download(ipa_url, file_ipa, md5=ipa_md5)

        with Block("打包"):
            Log("开始打包[%s]" % project)
            file_new = os.path.join("package", project, ipa_new)
            _update_state(process_url, worker, "resign")
            # noinspection PyBroadException
            _package(file_ipa, file_mp, cert, file_new)

        with Block("上传"):
            _update_state(process_url, worker, "upload_ipa")
            Log("上传ipa[%s][%s]" % (project, upload_url))
            rsp = requests.post(upload_url, files={
                "worker": worker,
                "file": read_binary_file(file_new),
            })
            assert rsp.status_code == 200
            assert rsp.json()["ret"] == 0
        Log("任务完成")
        _update_state(process_url, worker, "succ", fail=True)
        return {
            "succ": True,
            "uuid": uuid,
        }
    except:
        _update_state(process_url, worker, "fail")
