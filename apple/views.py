# Create your views here.
import datetime
import time
from typing import Dict, Union, List

import requests

from base.style import str_json, Assert, json_str, Log, Fail, to_form_url, now, Block, date_time_str
from frameworks.base import Action
from frameworks.db import db_mgr, db_session, db_model
from .models import IosDeviceInfo, IosAppInfo, IosCertInfo, IosProfileInfo


class AppleDeveloperConfig:
    def __init__(self, proj: str, account: str, password: str):
        self.proj = proj
        self.account = account
        self.password = password
        self.teams = []
        self.team_id = ""
        self.cookie = {}  # type: Dict[str,str]
        self.__expire = 0
        self.csrf = ""
        self.csrf_ts = ""

    def post(self, url: str, data: Dict = None, is_json=True, log=True, cache: Union[bool, int] = False, csrf=False):
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
            if rsp_str == "#NODATA#":
                headers = {
                    'cookie': to_form_url(self.cookie),
                }
                if csrf:
                    headers.update({
                        'csrf': self.csrf,
                        'csrf_ts': self.csrf_ts,
                    })
                rsp = requests.post(url, data=data, headers=headers)
                rsp_str = rsp.text
                Assert(rsp.status_code == 200, "请求异常")
                if rsp.headers.get("csrf"):
                    self.csrf = rsp.headers["csrf"]
                    self.csrf_ts = rsp.headers["csrf_ts"]
                if log:
                    Log("[%s]apple请求[%s]发送[%r]成功[%r]" % (now() - start, url, data, rsp_str))
                if cache:
                    _set_cache(url, data, rsp_str, expire=expire)
            if is_json:
                return str_json(rsp_str)
            else:
                return rsp_str
        except Exception as e:
            if log:
                Log("[%s]apple请求[%s]发送[%r]失败[%r]" % (now() - start, url, data, rsp_str))
            raise e

    def __logout(self):
        _key = "apple:developer:cookie"
        db_mgr.hdel(_key, self.account)
        self.__expire = 0
        self.cookie.clear()

    def __login(self):
        _key = "apple:developer:cookie"
        if self.__expire > now():
            return
        if not self.cookie:
            # 获取缓存
            self.cookie = str_json(db_mgr.hget(_key, self.account) or "{}")
        if not self.cookie:
            # 重新登录
            rsp = requests.post("https://idmsa.apple.com/appleauth/auth/signin", json={
                "accountName": self.account,
                "password": self.password,
                "rememberMe": True,
            }, headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                'X-Apple-Widget-Key': '16452abf721961a1728885bef033f28e',
            })
            Assert(rsp.status_code == 200)
            Assert(rsp.text.startswith("{"))
            self.cookie.update({
                "myacinfo": rsp.cookies["myacinfo"]
            })
            self.__expire = now() + 3600 * 1000
            db_mgr.hset(_key, self.account, json_str(self.cookie))
        Assert(self.cookie)
        # 验证登录
        rsp = requests.get("https://developer.apple.com/account/", headers={
            'cookie': to_form_url(self.cookie)
        })
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
            }).json()
            if ret["resultCode"] == 1100:
                self.__logout()
                raise Fail("请重新登录[%s]" % self.account)
            self.teams = ret["teams"]
            # Assert(self.teams[0]["type"] != "In-House")
            self.team_id = self.teams[0]["teamId"]
        Log("apple账号[%s:%s]登录成功" % (self.account, self.team_id))


def _cache(url: str, data: Dict):
    return db_session.get("http:cache:%s:%s" % (url, to_form_url(data)))


def _set_cache(url: str, data: Dict, content: str, expire: int):
    db_session.set("http:cache:%s:%s" % (url, to_form_url(data)), content, ex=expire // 1000)


def _reg_app(_config: AppleDeveloperConfig, app_id_id: str, name: str, prefix: str, identifier: str) -> str:
    sid = "%s:%s" % (_config.account, identifier)
    orig = str_json(db_model.hget("IosAppInfo:%s" % _config.account, identifier) or '{}')
    obj = {
        "identifier": identifier,
        "name": name,
        "prefix": prefix,
        "app_id_id": app_id_id,
        "app": _config.account,
    }
    if orig == obj:
        return app_id_id
    db_model.hset("IosAppInfo:%s" % _config.account, identifier, json_str(obj))
    _info = IosAppInfo()
    _info.sid = sid
    _info.app = _config.account
    _info.app_id_id = app_id_id
    _info.identifier = identifier
    _info.name = name
    _info.prefix = prefix
    _info.create = now()
    _info.save()
    Log("注册新的app[%s][%s][%s]" % (_config.account, app_id_id, identifier))
    return app_id_id


def _reg_cert(_config: AppleDeveloperConfig, cert_req_id, name, cert_id, sn, type_str, expire):
    sid = "%s:%s" % (_config.account, name)
    orig = str_json(db_model.get("IosCertInfo:%s:%s" % (_config.account, name)) or '{}')
    obj = {
        "name": name,
        "app": _config.account,
        "cert_req_id": cert_req_id,
        "cert_id": cert_id,
        "sn": sn,
        "type_str": type_str,
        "expire": expire,
        "expire_str": date_time_str(expire),
    }
    if orig == obj:
        return cert_req_id
    db_model.set("IosCertInfo:%s:%s" % (_config.account, name), json_str(obj), ex=(expire - now()) // 1000)
    _info = IosCertInfo()
    _info.sid = sid
    _info.app = _config.account
    _info.cert_req_id = cert_req_id
    _info.cert_id = cert_id
    _info.sn = sn
    _info.type_str = type_str
    _info.name = name
    _info.create = now()
    _info.expire = datetime.datetime.utcfromtimestamp(expire // 1000)
    _info.save()
    Log("注册新的证书[%s][%s]" % (name, cert_req_id))
    return cert_req_id


def _reg_device(device_id: str, udid: str, model: str, sn: str) -> str:
    orig = str_json(db_model.get("IosDeviceInfo:%s" % udid) or '{}')
    obj = {
        "udid": udid,
        "model": model,
        "sn": sn,
        "device_id": device_id,
    }
    if orig == obj:
        return udid
    db_model.set("IosDeviceInfo:%s" % udid, json_str(obj))
    _info = IosDeviceInfo()
    _info.udid = udid
    _info.device_id = device_id
    _info.model = model
    _info.sn = sn
    _info.create = now()
    _info.save()
    Log("注册新的设备[%s][%s][%s]" % (udid, device_id, sn))
    return udid


__config = {
    "test": AppleDeveloperConfig("test1", "liyiming@yomojoy.com", "Yomo151014"),
}  # type: Dict[str,AppleDeveloperConfig]


def _get_cert(_config: AppleDeveloperConfig) -> IosCertInfo:
    cert = IosCertInfo.objects.filter(
        app=_config.account,
        expire__gt=datetime.datetime.utcfromtimestamp(now() // 1000),
        type_str="development",
    ).first()  # type: IosCertInfo
    Assert("缺少现成的开发证书[%s]" % _config.account)
    return cert


def _get_app(_config: AppleDeveloperConfig) -> IosAppInfo:
    app = IosAppInfo.objects.filter(
        sid="%s:*" % _config.account,
    ).first()  # type: IosAppInfo
    return app


def _get_device_id(udid_list: List[str]) -> Dict[str, str]:
    return dict(
        zip(udid_list,
            map(lambda x: str_json(x)["device_id"] if x else x,
                db_model.mget(list(map(lambda x: "IosDeviceInfo:%s" % x, udid_list)))
                )
            )
    )


@Action
def init_app(app_id: str):
    _config = __config[app_id]
    with Block("添加设备"):
        ret = _config.post("https://developer.apple.com/services-account/QH65B2/account/ios/device/listDevices.action?teamId=", data={
            "includeRemovedDevices": True,
            "includeAvailability": True,
            "pageNumber": 1,
            "pageSize": 100,
            "sort": "status%3dasc",
            "teamId": _config.team_id,
        }, log=False)
        for device in ret["devices"]:  # type: Dict
            _reg_device(device["deviceId"],
                        device["deviceNumber"],
                        device.get("model", device.get("deviceClass", "#UNKNOWN#")),
                        device.get("serialNumber", "#UNKNOWN#"))
    with Block("同步app"):
        ret = _config.post(
            "https://developer.apple.com/services-account/QH65B2/account/ios/identifiers/listAppIds.action?teamId=", data={
                "pageNumber": 1,
                "pageSize": 500,
                "sort": "name%3dasc",
                "onlyCountLists": True,
            })
        for app in ret["appIds"]:  # type: Dict
            _reg_app(_config, app["appIdId"], app["name"], app["prefix"], app["identifier"])
    with Block("同步证书"):
        ret = _config.post("https://developer.apple.com/services-account/QH65B2/account/ios/certificate/listCertRequests.action?teamId=",
                           data={
                               "pageNumber": 1,
                               "pageSize": 500,
                               "sort": "certRequestStatusCode%3dasc",
                               "certificateStatus": 0,
                               "types": "5QPB9NHCEI",  # 证书类型
                           })
        for cert in ret["certRequests"]:  # type: Dict
            _reg_cert(_config,
                      cert["certRequestId"],
                      cert["name"],
                      cert["certificateId"],
                      cert["serialNum"],
                      cert["certificateType"]["permissionType"],
                      int(time.mktime(time.strptime(cert["expirationDate"].replace("Z", "UTC"), '%Y-%m-%dT%H:%M:%S%Z')) * 1000))


@Action
def download_profile(app_id: str):
    _config = __config[app_id]
    _info = IosProfileInfo.objects.filter(sid="%s" % _config.account).first()  # type: IosProfileInfo
    return {
        "encodedProfile": _info.profile,
    }


@Action
def add_device(app_id: str, udid: str):
    title = "设备%s" % udid
    _config = __config[app_id]
    if not db_model.get("IosDeviceInfo:%s" % udid):
        # 先注册设备
        ret = _config.post(
            "https://developer.apple.com/services-account/QH65B2/account/ios/device/validateDevices.action?teamId=", {
                "deviceNames": title,
                "deviceNumbers": udid,
                "register": "single",
                "teamId": _config.team_id,
            }, cache=True)

        Assert(ret["resultCode"] == 0, "验证udid请求失败[%s][%r]" % (udid, ret))
        Assert(len(ret["failedDevices"]) == 0, "验证udid请求失败[%s][%s]" % (udid, ret["validationMessages"]))
        _config.post("https://developer.apple.com/services-account/QH65B2/account/ios/device/listDevices.action?teamId=", data={
            "includeRemovedDevices": True,
            "includeAvailability": True,
            "pageNumber": 1,
            "pageSize": 1,
            "sort": "status%3dasc",
            "teamId": _config.team_id,
        }, log=False)
        ret = _config.post(
            "https://developer.apple.com/services-account/QH65B2/account/ios/device/addDevices.action?teamId=%s" % _config.team_id, {
                "deviceClasses": "iphone",
                "deviceNames": title,
                "deviceNumbers": udid,
                "register": "single",
                "teamId": _config.team_id,
            }, csrf=True)
        Assert(ret["resultCode"] == 0, "添加udid请求失败[%s]" % udid)
        Assert(not ret["validationMessages"], "添加udid请求失败[%s]" % udid)
        Assert(ret["devices"], "添加udid请求失败[%s]" % udid)
        device = ret["devices"][0]  # type: Dict
        _reg_device(device["deviceId"], device["deviceNumber"], device["model"], device["serialNumber"])

    _config = __config[app_id]
    with Block("更新"):
        ret = _config.post(
            "https://developer.apple.com/services-account/QH65B2/account/ios/profile/listProvisioningProfiles.action?teamId=",
            data={
                "includeInactiveProfiles": True,
                "onlyCountLists": True,
                "sidx": "name",
                "sort": "name%3dasc",
                "teamId": _config.team_id,
                "pageNumber": 1,
                "pageSize": 500,
            })
        _info = IosProfileInfo.objects.filter(sid="%s" % _config.account, app=_config.account).first()  # type:IosProfileInfo
        if not _info:
            _info = IosProfileInfo()
            _info.sid = "%s" % _config.account
            _info.app = _config.account
            _info.devices = ""
            _info.save()
        devices = _info.devices.split(",") if _info.devices else []
        device_id = _get_device_id([udid])[udid]
        if device_id in devices:
            pass
        else:
            devices.append(device_id)
            _info.devices = ",".join(devices)
            _app = _get_app(_config)
            _cert = _get_cert(_config)
            found = False
            for each in ret["provisioningProfiles"]:  # type: Dict
                if each["name"] != "专用 %s" % _config.proj:
                    continue

                ret = _config.post(
                    "https://developer.apple.com/services-account/QH65B2/account/ios/profile/regenProvisioningProfile.action?teamId=",
                    data={
                        "provisioningProfileId": each["provisioningProfileId"],
                        "distributionType": "limited",
                        "subPlatform": "",
                        "returnFullObjects": False,
                        "provisioningProfileName": each["name"],
                        "appIdId": _app.app_id_id,
                        "certificateIds": _cert.cert_req_id,
                        "deviceIds": ",".join(devices),
                    }, csrf=True)
                Assert(ret["resultCode"] == 0)
                _info.profile_id = each["provisioningProfileId"]
                # noinspection PyTypeChecker
                _info.profile = ret["provisioningProfile"]["encodedProfile"]
                _info.save()
                found = True
                Log("更新证书[%s]添加设备[%s]成功" % (_config.proj, udid))
                break
            if not found:
                ret = _config.post(
                    "https://developer.apple.com/services-account/QH65B2/account/ios/profile/createProvisioningProfile.action?teamId=",
                    data={
                        "subPlatform": "",
                        "certificateIds": _cert.cert_req_id,
                        "deviceIds": ",".join(devices),
                        "template": "",
                        "returnFullObjects": False,
                        "distributionTypeLabel": "distributionTypeLabel",
                        "distributionType": "limited",
                        "appIdId": _app.app_id_id,
                        "appIdName": _app.name,
                        "appIdPrefix": _app.prefix,
                        "appIdIdentifier": _app.identifier,
                        "provisioningProfileName": "专用 %s" % _config.proj,
                    }, csrf=True)
                Assert(ret["resultCode"] == 0)
                # noinspection PyTypeChecker
                _info.profile_id = ret["provisioningProfile"]["provisioningProfileId"]
                # noinspection PyTypeChecker
                _info.profile = ret["provisioningProfile"]["encodedProfile"]
                _info.save()
                Log("添加证书[%s]添加设备[%s]成功" % (_config.proj, udid))

    return {
        "succ": True,
    }
