import argparse
import os
import re
import shlex
import time
from collections import OrderedDict, namedtuple
from http.cookies import SimpleCookie
from typing import Dict, Union

import requests

from base.style import str_json, now, to_form_url, Assert, Log, json_str, Fail, str_json_i
from base.utils import base64, base64decode
from frameworks.db import db_session, db_mgr, message_from_topic
from .models import IosAccountInfo

_default_headers = {
    'X-Apple-Widget-Key': '83545bf919730e51dbfba24e7e8a78d2',
    'Origin': 'https://idmsa.apple.com',
    'Accept-Encoding': 'gzip, deflate, br',
    'X-Apple-I-FD-Client-Info': '{"U":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36","L":"en-US","Z":"GMT+08:00","V":"1.1","F":"7Wa44j1e3NlY5BSo9z4ofjb75PaK4Vpjt3Q9cUVlOrXTAxw63UYOKES5jfzmkflJfmNzl998tp7ppfAaZ6m1CdC5MQjGejuTDRNziCvTDfWk2Lwox0fEeMqgXK_Pmtd0SHp815LyjaY2.rINj.rINYOK0UjVsYUMnGWFfwMHDCQyG5me6sBLSsbXzU0l6sqKIrGfuzwg9wK9waEwHXXTSHCSPmtd0wVYPIG_qvoPfybYb5EvYTrYesR.pjCEFPnu_xf7_OLgiPFMtrs1OeyjaY2hDpBtOtJJIqSI6KUMnGWpwoNSUC56MnGW87gq1HACVd_8I9N9V4B5zLwBdo72_AIQjJKy_Aw7Q_14Ygh5Dwhw.Tf5.EKVg8o7I_3Divp8UaWUe0SFQ_14YefhSWHWY5BNveBBNlYCa1nkBMfs.DBR"}',
    'Accept-Language': 'en-US,en;q=0.9,la;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://idmsa.apple.com/appleauth/auth/signin?widgetKey=83545bf919730e51dbfba24e7e8a78d2&locale=en_US&font=sf',
    'X-Requested-With': 'XMLHttpRequest',
    'Connection': 'keep-alive',
}

__HOST = os.environ.get("VIRTUAL_HOST", "127.0.0.1:8000")


def entry(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return "http://%s%s" % (__HOST, path)


def _cache(url: str, data: Dict):
    return db_session.get("http:cache:%s:%s" % (url, to_form_url(data)))


def _set_cache(url: str, data: Dict, content: str, expire: int):
    db_session.set("http:cache:%s:%s" % (url, to_form_url(data)), content, ex=expire // 1000)


__pub = db_session.pubsub()
__pub.subscribe("account:security:code")


def publish_security_code(account: str, code: str, ts: int):
    db_session.publish("account:security:code", json_str({
        "account": account,
        "code": code,
        "ts": ts,
    }))


def get_capability(cate: str):
    if cate == "GAME_CENTER":
        return {
            "type": "bundleIdCapabilities",
            "attributes": {
                "enabled": True,
                "settings": [],
            },
            "relationships": {
                "capability": {
                    "data": {
                        "type": "capabilities",
                        "id": "GAME_CENTER",
                    },
                },
            },
        }
    elif cate == "IN_APP_PURCHASE":
        return {
            "type": "bundleIdCapabilities",
            "attributes": {
                "enabled": True,
                "settings": [],
            },
            "relationships": {
                "capability": {
                    "data": {
                        "type": "capabilities",
                        "id": "IN_APP_PURCHASE",
                    },
                },
            },
        }
    else:
        raise Fail("不支持的capability[%s]" % cate)


def _wait_code(info: IosAccountInfo, session: requests.Session, ts):
    """
    等待二次提交的需要
    """
    Log("等待二次验证")
    # last = info.security_code
    last = ""
    expire = now() + 1200 * 1000
    while now() < expire:
        time.sleep(1)
        for data in message_from_topic(__pub, is_json=True, limit=1):
            if data.get("account") == info.account and data.get("ts") > ts:
                if data.get("code") != last:
                    rsp = session.post("https://idmsa.apple.com/appleauth/auth/verify/trusteddevice/securitycode", json={
                        "securityCode": {"code": data["code"]},
                    }, headers=_default_headers)
                    if rsp.status_code != 204:
                        continue
                    rsp = session.post("https://idmsa.apple.com/appleauth/auth/2sv/trust", json={

                    })
                    if rsp.status_code == 204:
                        return session
    raise Fail("登录二次验证超时")


class IosAccountHelper:
    def __init__(self, info: IosAccountInfo):
        self.info = info
        self.account = info.account
        self.password = info.password
        self.teams = str_json(info.teams)
        self.team_id = info.team_id
        self.headers = str_json(info.headers)
        self.cookie = str_json(info.cookie)  # type: Dict[str,str]
        self.csrf = info.csrf
        self.csrf_ts = info.csrf_ts
        self.session = requests.session()
        # self.session.headers.update(self.headers)
        # self.session.cookies.update(self.cookie)

    def post(self, title: str, url: str, data: Union[Dict, str] = None, is_json=True, log=True, cache: Union[bool, int] = False, csrf=False,
             json_api=True, method="POST", is_binary=False, ex_headers=None, status=200):
        if cache is True:
            expire = 3600 * 1000
        else:
            expire = cache

        if not self.cookie:
            self.__login()
        start = now()
        rsp_str = "#NODATA#"
        try:
            if "teamId=" in url:
                if "teamId=%s" % self.team_id not in url:
                    url = url.replace("teamId=", "teamId=%s" % self.team_id)
            if cache:
                rsp_str = _cache(url, data) or rsp_str
            headers = {
                'cookie': to_form_url({"myacinfo": self.cookie["myacinfo"]}),
            }
            if csrf:
                headers.update({
                    'csrf': self.csrf,
                    'csrf_ts': self.csrf_ts,
                })
            if ex_headers:
                headers.update(ex_headers)
            if rsp_str == "#NODATA#":
                if method.upper() == "GET":
                    rsp = requests.get(url, params=data, headers=headers, timeout=3)
                else:
                    rsp = requests.post(url, data=data, headers=headers, timeout=3)

                rsp_str = rsp.text
                if rsp.headers.get("csrf"):
                    self.csrf = rsp.headers["csrf"]
                    self.csrf_ts = rsp.headers["csrf_ts"]
                Assert(rsp.status_code == status, "请求[%s]异常[%s]" % (title, rsp.status_code))
                if json_api:
                    _data = str_json_i(rsp_str) or {}
                    if _data.get("resultCode") == 1100:
                        self.__logout()
                        raise Fail("登录[%s]过期了[%s][%s]" % (self.account, _data.get("resultString"), _data.get("userString")))
                    Assert(_data.get("resultCode") == 0, "请求业务[%s]失败[%s][%s]" % (title, _data.get("resultString"), _data.get("userString")))
                if log:
                    Log("apple请求[%s][%s]发送[%r]成功[%r]" % (title, now() - start, data, rsp_str))
                if is_binary:
                    rsp_str = base64(rsp.content)
                if cache:
                    _set_cache(url, data, rsp_str, expire=expire)
            if is_json:
                return str_json(rsp_str)
            elif is_binary:
                return base64decode(rsp_str)
            else:
                return rsp_str
        except Exception as e:
            if log:
                Log("apple请求[%s][%s]发送[%r]失败[%r]" % (title, now() - start, data, rsp_str))
            raise e

    @property
    def is_login(self):
        return "myacinfo" in self.cookie

    def __save_cookie(self, cookie: Dict):
        _orig = self.info.cookie
        _new = json_str(cookie)
        if _orig == _new:
            return
        self.info.cookie = _new
        self.info.save()

    def __logout(self):
        _key = "apple:developer:cookie"
        db_mgr.hdel(_key, self.account)
        self.__expire = 0
        self.cookie.clear()

    def __login(self):
        _key = "apple:developer:cookie"
        if self.csrf_ts > now():
            return
        if not self.is_login:
            # 重新登录
            rsp = self.session.post("https://idmsa.apple.com/appleauth/auth/signin", json={
                "accountName": self.account,
                "password": self.password,
                "rememberMe": True,
            }, headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Apple-Widget-Key": '16452abf721961a1728885bef033f28e',
                "Cookie": to_form_url(self.cookie),
            }, timeout=3)
            if rsp.status_code == 409:
                # 二次验证
                _wait_code(self.info, self.session, now())

            Assert(rsp.status_code == 200)
            Assert(rsp.text.startswith("{"))
            self.cookie.update({
                "myacinfo": rsp.cookies["myacinfo"]
            })
            self.__expire = now() + 3600 * 1000
            db_mgr.hset(_key, self.account, json_str(self.cookie))
        Assert(self.cookie)
        # 验证登录
        rsp = self.session.get("https://developer.apple.com/account/")
        Assert(rsp.status_code == 200)
        if rsp.text.startswith("{"):
            _ret = str_json(rsp.text)
            if _ret["resultCode"] == 5003 or "NotAuthenticated" in _ret["resultString"]:
                # 登录失败了
                raise Fail("登录失败了[%s:%s][%s]" % (self.account, self.password, rsp.text))
        if not self.team_id:
            ret = requests.post("https://developer.apple.com/services-account/QH65B2/account/listTeams.action", headers={
                "Content-Length": "0",
                'cookie': to_form_url(self.cookie),
            }, timeout=3).json()
            if ret["resultCode"] == 1100:
                self.__logout()
                raise Fail("请重新登录[%s]" % self.account)
            self.teams = ret["teams"]
            # Assert(self.teams[0]["type"] != "In-House")
            self.team_id = self.teams[0]["teamId"]
        Log("apple账号[%s:%s]登录成功" % (self.account, self.team_id))


parser = argparse.ArgumentParser()
parser.add_argument('command')
parser.add_argument('url')
parser.add_argument('-d', '--data')
parser.add_argument('-b', '--data-binary', default=None)
parser.add_argument('-X', default='')
parser.add_argument('-H', '--header', action='append', default=[])
parser.add_argument('--compressed', action='store_true')
parser.add_argument('--insecure', action='store_true')
ParsedContext = namedtuple('ParsedContext', ['method', 'url', 'data', 'headers', 'cookies', 'verify'])


def curl_parse_context(curl_command):
    method = "get"

    tokens = shlex.split(curl_command)
    parsed_args = parser.parse_args(tokens)

    post_data = parsed_args.data or parsed_args.data_binary
    if post_data:
        method = 'post'

    if parsed_args.X:
        method = parsed_args.X.lower()

    cookie_dict = OrderedDict()
    quoted_headers = OrderedDict()

    for curl_header in parsed_args.header:
        if curl_header.startswith(':'):
            occurrence = [m.start() for m in re.finditer(':', curl_header)]
            header_key, header_value = curl_header[:occurrence[1]], curl_header[occurrence[1] + 1:]
        else:
            header_key, header_value = curl_header.split(":", 1)

        if header_key.lower() == 'cookie':
            cookie = SimpleCookie(header_value)
            for key in cookie:
                cookie_dict[key] = cookie[key].value
        else:
            quoted_headers[header_key] = header_value.strip()

    return ParsedContext(
        method=method,
        url=parsed_args.url,
        data=post_data,
        headers=quoted_headers,
        cookies=cookie_dict,
        verify=parsed_args.insecure
    )
