# Create your views here.
import datetime
import os
import time
import uuid
from typing import Dict, List, Callable, Optional

import requests
from django.http import HttpResponseRedirect

from base.style import str_json, Assert, json_str, Log, now, Block, date_time_str, Fail, Trace
from frameworks.base import Action
from frameworks.db import db_model, db_session
from .models import IosDeviceInfo, IosAppInfo, IosCertInfo, IosProfileInfo, IosAccountInfo, UserInfo, IosProjectInfo
from .utils import IosAccountHelper, publish_security_code, curl_parse_context


def _reg_app(_config: IosAccountInfo, app_id_id: str, name: str, prefix: str, identifier: str) -> str:
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


def _reg_cert(_config: IosAccountInfo, cert_req_id, name, cert_id, sn, type_str, expire):
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


def _get_cert(info: IosAccountInfo) -> IosCertInfo:
    cert = IosCertInfo.objects.filter(
        app=info.account,
        expire__gt=datetime.datetime.utcfromtimestamp(now() // 1000),
        type_str="development",
    ).first()  # type: IosCertInfo
    return Assert(cert, "缺少现成的开发[iOS App Development]证书[%s]" % info.account)


def _get_app(info: IosAccountInfo) -> IosAppInfo:
    app = IosAppInfo.objects.filter(
        sid="%s:*" % info.account,
    ).first()  # type: IosAppInfo
    return Assert(app, "缺少app")


def _get_device_id(udid_list: List[str]) -> Dict[str, str]:
    return dict(
        zip(udid_list,
            map(lambda x: str_json(x)["device_id"] if x else x,
                db_model.mget(list(map(lambda x: "IosDeviceInfo:%s" % x, udid_list)))
                )
            )
    )


def __list_all_app(_config: IosAccountHelper):
    ret = _config.post(
        "所有的app",
        "https://developer.apple.com/services-account/QH65B2/account/ios/identifiers/listAppIds.action?teamId=",
        data={
            "pageNumber": 1,
            "pageSize": 500,
            "sort": "name%3dasc",
            "onlyCountLists": True,
        })
    for app in ret["appIds"]:  # type: Dict
        _reg_app(_config.info, app["appIdId"], app["name"], app["prefix"], app["identifier"])


def __list_all_cert(_config: IosAccountHelper):
    ret = _config.post(
        "所有的证书",
        "https://developer.apple.com/services-account/QH65B2/account/ios/certificate/listCertRequests.action?teamId=",
        data={
            "pageNumber": 1,
            "pageSize": 500,
            "sort": "certRequestStatusCode%3dasc",
            "certificateStatus": 0,
            "types": "5QPB9NHCEI",  # 证书类型
        })
    for cert in ret["certRequests"]:  # type: Dict
        _reg_cert(_config.info,
                  cert["certRequestId"],
                  cert["name"],
                  cert["certificateId"],
                  cert["serialNum"],
                  cert["certificateType"]["permissionType"],
                  int(time.mktime(time.strptime(cert["expirationDate"].replace("Z", "UTC"), '%Y-%m-%dT%H:%M:%S%Z')) * 1000))


@Action
def init_account(account: str):
    _config = IosAccountHelper(IosAccountInfo.objects.filter(account=account).first())
    __list_all_devices(_config)
    __list_all_app(_config)
    __list_all_cert(_config)
    return {
        "succ": True,
    }


@Action
def download_profile(uuid: str):
    """
    基于用户id下载
    """
    _user = UserInfo.objects.filter(uuid=uuid).first()  # type: UserInfo
    Assert(_user is not None, "没有找到uuid[%s]" % uuid)
    _config = IosAccountHelper(IosAccountInfo.objects.filter(account=_user.account).first())
    _info = IosProfileInfo.objects.filter(sid="%s" % _config.account).first()  # type: IosProfileInfo
    return {
        "encodedProfile": _info.profile,
    }


@Action
def newbee(project: str):
    """
    根据项目生成具体的一个可以注册新设备的uuid
    """
    _info = IosProjectInfo.objects.filter(project=project).first()  # type: IosProjectInfo
    Assert(_info is not None, "找不到对应的项目[%s]" % project)
    _uuid = ""
    with Block("生成一个新的uuid提供给外部下载"):
        # 默认一天的时效
        for _ in range(100):
            _uuid = uuid.uuid4()
            if db_session.set("uuid:%s" % _uuid, json_str({
                "project": _info.project,
            }), ex=3600 * 24, nx=True):
                break
    return {
        "uuid": str(_uuid),
    }


def __fetch_account(udid: str, action: Callable[[IosAccountInfo, str], bool]) -> IosAccountInfo:
    """
    循环使用所有的账号
    """
    for each in IosAccountInfo.objects.filter(devices_num__lt=100):
        if action(each, udid):
            return each
    raise Fail("没有合适的账号了")


def __list_all_devices(_config: IosAccountHelper):
    ret = _config.post(
        "获取所有的列表",
        "https://developer.apple.com/services-account/QH65B2/account/ios/device/listDevices.action?teamId=",
        data={
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
    # 更新一下info
    devices = list(map(lambda x: x["deviceNumber"], ret["devices"]))
    if json_str(devices) != _config.info.devices:
        Log("更新设备列表[%s]数量[%s]=>[%s]" % (_config.account, _config.info.devices_num, len(devices)))
        _config.info.devices = json_str(devices)
        _config.info.devices_num = len(devices)
        _config.info.save()


def __add_device(account: IosAccountInfo, udid: str, project: str = "package") -> bool:
    title = "设备%s" % udid
    _config = IosAccountHelper(account)
    try:
        _device = IosDeviceInfo.objects.filter(udid=udid).first()  # type:Optional[IosDeviceInfo]
        if not _device:
            # 先注册设备
            ret = _config.post(
                "验证设备udid",
                "https://developer.apple.com/services-account/QH65B2/account/ios/device/validateDevices.action?teamId=", {
                    "deviceNames": title,
                    "deviceNumbers": udid,
                    "register": "single",
                    "teamId": _config.team_id,
                }, cache=True)

            Assert(len(ret["failedDevices"]) == 0, "验证udid请求失败[%s][%s]" % (udid, ret["validationMessages"]))
            __list_all_devices(_config)
            ret = _config.post(
                "添加设备",
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

        with Block("更新"):
            ret = _config.post(
                "更新列表",
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
                _app = _get_app(_config.info)
                _cert = _get_cert(_config.info)
                found = False
                for each in ret["provisioningProfiles"]:  # type: Dict
                    if each["name"] != "专用 %s" % project:
                        continue
                    # todo: 过期更新
                    ret = _config.post(
                        "更新ProvisioningProfile",
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
                    Log("更新证书[%s]添加设备[%s]成功" % (project, udid))
                    break
                if not found:
                    ret = _config.post(
                        "创建ProvisioningProfile",
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
                            "provisioningProfileName": "专用 %s" % project,
                        }, csrf=True)
                    Assert(ret["resultCode"] == 0)
                    # noinspection PyTypeChecker
                    _info.profile_id = ret["provisioningProfile"]["provisioningProfileId"]
                    # noinspection PyTypeChecker
                    _info.profile = ret["provisioningProfile"]["encodedProfile"]
                    _info.save()
                    Log("添加证书[%s]添加设备[%s]成功" % (project, udid))
    except Exception as e:
        Trace("添加设备出错了[%s]" % e, e)
        return False
    return True


def __add_task(_user: UserInfo):
    _account = IosAccountInfo.objects.filter(account=_user.account).first()  # type:IosAccountInfo
    _project = IosProjectInfo.objects.filter(project=_user.project).first()  # type:IosProjectInfo
    db_session.publish("task:package", json_str({
        "cert": "iPhone Developer: zhangming luo",
        "cert_p12": "",
        "mobileprovision": "MIIduAYJKoZIhvcNAQcCoIIdqTCCHaUCAQExCzAJBgUrDgMCGgUAMIINTAYJKoZIhvcNAQcBoIINPQSCDTk8P3htbCB2ZXJzaW9uPSIxLjAiIGVuY29kaW5nPSJVVEYtOCI/Pgo8IURPQ1RZUEUgcGxpc3QgUFVCTElDICItLy9BcHBsZS8vRFREIFBMSVNUIDEuMC8vRU4iICJodHRwOi8vd3d3LmFwcGxlLmNvbS9EVERzL1Byb3BlcnR5TGlzdC0xLjAuZHRkIj4KPHBsaXN0IHZlcnNpb249IjEuMCI+CjxkaWN0PgoJPGtleT5BcHBJRE5hbWU8L2tleT4KCTxzdHJpbmc+WGNvZGUgaU9TIFdpbGRjYXJkIEFwcCBJRDwvc3RyaW5nPgoJPGtleT5BcHBsaWNhdGlvbklkZW50aWZpZXJQcmVmaXg8L2tleT4KCTxhcnJheT4KCTxzdHJpbmc+S1JFWTYzQ0ZSNjwvc3RyaW5nPgoJPC9hcnJheT4KCTxrZXk+Q3JlYXRpb25EYXRlPC9rZXk+Cgk8ZGF0ZT4yMDE5LTAzLTEwVDEyOjQ1OjM0WjwvZGF0ZT4KCTxrZXk+UGxhdGZvcm08L2tleT4KCTxhcnJheT4KCQk8c3RyaW5nPmlPUzwvc3RyaW5nPgoJPC9hcnJheT4KICAgIDxrZXk+SXNYY29kZU1hbmFnZWQ8L2tleT4KICAgIDxmYWxzZS8+Cgk8a2V5PkRldmVsb3BlckNlcnRpZmljYXRlczwva2V5PgoJPGFycmF5PgoJCTxkYXRhPk1JSUZtakNDQklLZ0F3SUJBZ0lJZlkzRTUvVVdHVWd3RFFZSktvWklodmNOQVFFTEJRQXdnWll4Q3pBSkJnTlZCQVlUQWxWVE1STXdFUVlEVlFRS0RBcEJjSEJzWlNCSmJtTXVNU3d3S2dZRFZRUUxEQ05CY0hCc1pTQlhiM0pzWkhkcFpHVWdSR1YyWld4dmNHVnlJRkpsYkdGMGFXOXVjekZFTUVJR0ExVUVBd3c3UVhCd2JHVWdWMjl5YkdSM2FXUmxJRVJsZG1Wc2IzQmxjaUJTWld4aGRHbHZibk1nUTJWeWRHbG1hV05oZEdsdmJpQkJkWFJvYjNKcGRIa3dIaGNOTVRneE1ESXpNREV6TVRVd1doY05NVGt4TURJek1ERXpNVFV3V2pDQmpURWFNQmdHQ2dtU0pvbVQ4aXhrQVFFTUNqSlNOa000UTFaWk4wY3hOVEF6QmdOVkJBTU1MR2xRYUc5dVpTQkVaWFpsYkc5d1pYSTZJSHBvWVc1bmJXbHVaeUJzZFc4Z0tGcE1PRmhJVkRjNU5EUXBNUk13RVFZRFZRUUxEQXBMVWtWWk5qTkRSbEkyTVJZd0ZBWURWUVFLREExNmFHRnVaMjFwYm1jZ2JIVnZNUXN3Q1FZRFZRUUdFd0pWVXpDQ0FTSXdEUVlKS29aSWh2Y05BUUVCQlFBRGdnRVBBRENDQVFvQ2dnRUJBTVA5MENUN0RjR21iVE5sWFBVMFNpYy9TcE5sdXBiZ3ZRM3pqWG94bmxGT0ZrZi9tWTAwN1J0MEVJREw5WDNoWHlEVGtaMGpGV2pVRk5IVFVUeDZxRFlyUCtBdXlHTE1NbnZ4V1dCbWtZMUZHUUt6Z0ZkdWNSc3VXcVFVK2tBWmlmRm9wRWw3Mkk5eit4ZkE1WFJqc1ZDeUtOTGhuV3o1VFRxbkp5MmVCbG5BenU5dlBxSDNYd282Mm0rTC96ekhOeWg1M0c1QnJZa2VZYkUyQ0VaTE9MWXdHZWp0TUljYjhsYXUrSG54TGpxc1BUTDNiNFArek5FcmxwdTlSTmVWSEpkMHcxQml4NisvcjFSekkzQUtObnZITDR5QUphaktxYzFhM0pjbGJLQ0FhQ1FZMlQxT3phNHVqQTkzaXlKTVBvYXpqSlpOV1N3ZXJWNWJ6ZVVhc2k4Q0F3RUFBYU9DQWZFd2dnSHRNQXdHQTFVZEV3RUIvd1FDTUFBd0h3WURWUjBqQkJnd0ZvQVVpQ2NYQ2FtMkdHQ0w3T3U2OWtkWnhWSlVvN2N3UHdZSUt3WUJCUVVIQVFFRU16QXhNQzhHQ0NzR0FRVUZCekFCaGlOb2RIUndPaTh2YjJOemNDNWhjSEJzWlM1amIyMHZiMk56Y0RBekxYZDNaSEl3TVRDQ0FSMEdBMVVkSUFTQ0FSUXdnZ0VRTUlJQkRBWUpLb1pJaHZkalpBVUJNSUgrTUlIREJnZ3JCZ0VGQlFjQ0FqQ0J0Z3lCczFKbGJHbGhibU5sSUc5dUlIUm9hWE1nWTJWeWRHbG1hV05oZEdVZ1lua2dZVzU1SUhCaGNuUjVJR0Z6YzNWdFpYTWdZV05qWlhCMFlXNWpaU0J2WmlCMGFHVWdkR2hsYmlCaGNIQnNhV05oWW14bElITjBZVzVrWVhKa0lIUmxjbTF6SUdGdVpDQmpiMjVrYVhScGIyNXpJRzltSUhWelpTd2dZMlZ5ZEdsbWFXTmhkR1VnY0c5c2FXTjVJR0Z1WkNCalpYSjBhV1pwWTJGMGFXOXVJSEJ5WVdOMGFXTmxJSE4wWVhSbGJXVnVkSE11TURZR0NDc0dBUVVGQndJQkZpcG9kSFJ3T2k4dmQzZDNMbUZ3Y0d4bExtTnZiUzlqWlhKMGFXWnBZMkYwWldGMWRHaHZjbWwwZVM4d0ZnWURWUjBsQVFIL0JBd3dDZ1lJS3dZQkJRVUhBd013SFFZRFZSME9CQllFRkV1V3FnelpKdTlHL3dRWWZ0S0RKTkF3cklmck1BNEdBMVVkRHdFQi93UUVBd0lIZ0RBVEJnb3Foa2lHOTJOa0JnRUNBUUgvQkFJRkFEQU5CZ2txaGtpRzl3MEJBUXNGQUFPQ0FRRUFJZWNQdCt6Z2xoZlkwVFc0UHl2ZUNlTHQxOENZa2t5N2NZRjZKa1FEa2RCYzFuN0xVU04rWjlobjd6TUp3UUx0Z041QkJRV1VuNDdkQW9Hc3AzV3FOb2czQzFobG9qSkNGeWc3Q0pIOWpKK0d6ZFlCZUFCeTBWMCs5Zkp6SXREcHdmTm5kWnpjTjUrM25KYUF5cW1uNnhnM3pBbDVjVjR4NWxFeGRCNWNWWUNkZDJmMkdxZHVZckVpdExma3ZkVFVJNGZyQXhaZnlsdWtBUEZiNFczc09sdytjcWl4L0Q1R0xGYUNCLzZhc0tFblpDam1XVCthR1pQczEzWXZtQ2M0RldzVVBwUzB2Qk0rMVB5VEEzdlBaUThaZzkwVVFreFVrK1FHZnhPSzJLeVRyVmhRQnIyUTZCYkhBQmgxZ3FmcEZ5WWpPdG0vWnRBa1VnejU5VlNkN2c9PTwvZGF0YT4KCTwvYXJyYXk+CgoKCTxrZXk+RW50aXRsZW1lbnRzPC9rZXk+Cgk8ZGljdD4KCQk8a2V5PmtleWNoYWluLWFjY2Vzcy1ncm91cHM8L2tleT4KCQk8YXJyYXk+CgkJCTxzdHJpbmc+S1JFWTYzQ0ZSNi4qPC9zdHJpbmc+CQkKCQk8L2FycmF5PgoJCTxrZXk+Z2V0LXRhc2stYWxsb3c8L2tleT4KCQk8dHJ1ZS8+CgkJPGtleT5hcHBsaWNhdGlvbi1pZGVudGlmaWVyPC9rZXk+CgkJPHN0cmluZz5LUkVZNjNDRlI2Lio8L3N0cmluZz4KCQk8a2V5PmNvbS5hcHBsZS5kZXZlbG9wZXIudGVhbS1pZGVudGlmaWVyPC9rZXk+CgkJPHN0cmluZz5LUkVZNjNDRlI2PC9zdHJpbmc+CgoJPC9kaWN0PgoJPGtleT5FeHBpcmF0aW9uRGF0ZTwva2V5PgoJPGRhdGU+MjAyMC0wMy0wOVQxMjo0NTozNFo8L2RhdGU+Cgk8a2V5Pk5hbWU8L2tleT4KCTxzdHJpbmc+JiMxOTk4NzsmIzI5OTkyOyBwYWNrYWdlPC9zdHJpbmc+Cgk8a2V5PlByb3Zpc2lvbmVkRGV2aWNlczwva2V5PgoJPGFycmF5PgoJCTxzdHJpbmc+MDAwMDgwMjAtMDAwOTU4ODIwQTYyMDAyRTwvc3RyaW5nPgoJCTxzdHJpbmc+YmI3ZDgxOGY0ODAyNjJhNmMwZjU5NzUxOTcxNTcyNmNjYjE4Y2M1Yzwvc3RyaW5nPgoJPC9hcnJheT4KCTxrZXk+VGVhbUlkZW50aWZpZXI8L2tleT4KCTxhcnJheT4KCQk8c3RyaW5nPktSRVk2M0NGUjY8L3N0cmluZz4KCTwvYXJyYXk+Cgk8a2V5PlRlYW1OYW1lPC9rZXk+Cgk8c3RyaW5nPnpoYW5nbWluZyBsdW88L3N0cmluZz4KCTxrZXk+VGltZVRvTGl2ZTwva2V5PgoJPGludGVnZXI+MzY1PC9pbnRlZ2VyPgoJPGtleT5VVUlEPC9rZXk+Cgk8c3RyaW5nPjA3OWYyODZlLTkwODktNDdjMi1hOTI3LWE3NTlmZTY4OTdlMzwvc3RyaW5nPgoJPGtleT5WZXJzaW9uPC9rZXk+Cgk8aW50ZWdlcj4xPC9pbnRlZ2VyPgo8L2RpY3Q+CjwvcGxpc3Q+oIINsTCCA/MwggLboAMCAQICARcwDQYJKoZIhvcNAQEFBQAwYjELMAkGA1UEBhMCVVMxEzARBgNVBAoTCkFwcGxlIEluYy4xJjAkBgNVBAsTHUFwcGxlIENlcnRpZmljYXRpb24gQXV0aG9yaXR5MRYwFAYDVQQDEw1BcHBsZSBSb290IENBMB4XDTA3MDQxMjE3NDMyOFoX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",
        "project": _project.project,
        "ipa_url": _asset_url("%s/orig.ipa" % _user.project),
        "ipa_md5": _project.md5sum,
        "ipa_new": "%s_%s.ipa" % (_account.team_id, _account.devices_num),
        "upload_url": "http://127.0.0.1:8000/apple/upload_ipa?project=%s&account=%s" % (_user.project, _user.account),
        "ts": now(),
    }))


# noinspection PyShadowingNames
@Action
def add_device(uuid: str, udid: str):
    _key = "uuid:%s" % uuid
    _detail = str_json(db_session.get(_key) or "{}")
    if not _detail:
        raise Fail("添加失败")
    _account = None
    for _user in UserInfo.objects.filter(udid=udid):
        _account = _user.account
        if _user.project == _detail["project"]:
            if uuid != _user.uuid:
                uuid = _user.uuid
                break

    if not _account:
        _account = __fetch_account(udid, __add_device)
    else:
        _account = IosAccountInfo.objects.filter(account=_account).first()

    _user = UserInfo(uuid=uuid)
    _user.udid = udid
    _user.project = _detail["project"]
    _user.account = _account.account
    _user.save()
    # db_session.delete(_key)
    Log("添加成了[%s][%s]" % (udid, _account.account))
    __add_task(_user)
    return {
        "succ": True,
    }


@Action
def security_code(account: str, code: str):
    publish_security_code(account, code, now())
    return {
        "succ": True,
    }


@Action
def login_by_curl(cmd: str):
    """
    https://developer.apple.com/account/#/overview/QLDV8FPKZC
    getUserProfile 请求

    curl 'https://developer.apple.com/services-account/QH65B2/account/getUserProfile' -H 'origin: https://developer.apple.com' -H 'accept-encoding: gzip, deflate, br' -H 'accept-language: zh-CN,zh;q=0.9' -H 'csrf: cf0796aee015fe0f03e7ccc656ba4b898b696cc1072027988d89b1f6e607fd67' -H 'cookie: geo=SG; ccl=SR+vWVA/vYTrzR1LkZE2tw==; s_fid=56EE3E795513A2B4-16F81B5466B36881; s_cc=true; s_vi=[CS]v1|2E425B0B852E2C90-40002C5160000006[CE]; dslang=CN-ZH; site=CHN; s_pathLength=developer%3D2%2C; acn01=v+zxzKnMyleYWzjWuNuW1Y9+kAJBxfozY2UAH0paNQB+FA==; myacinfo=DAWTKNV2a5c238e8d27e8ed221c8978cfb02ea94b22777f25ffec5abb1a855da8debe4f59d60b506eae457dec4670d5ca9663ed72c3d1976a9f87c53653fae7c63699abe64991180d7c107c50ce88be233047fc96de200c3f23947bfbf2e064c7b9a7652002d285127345fe15adf53bab3d347704cbc0a8b856338680722e5d0387a5eb763d258cf19b79318be28c4abd01e27029d2ef26a1bd0dff61d141380a1b496b92825575735d0be3dd02a934db2d788c9d6532b6a36bc69d244cc9b4873cef8f4a3a90695f172f6f521330f67f20791fd7d62dfc9d6de43899ec26a8485191d62e2c5139f81fca2388d57374ff31f9f689ad373508bcd74975ddd3d3b7875fe3235323962636433633833653433363562313034383164333833643736393763303538353038396439MVRYV2; DSESSIONID=1c3smahkpfbkp7k3fju30279uoba8p8480gs5ajjgsbbvn8lubqt; s_sq=%5B%5BB%5D%5D' -H 'user-locale: en_US' -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.81 Safari/537.36 QQBrowser/4.5.122.400' -H 'content-type: application/json' -H 'accept: application/json' -H 'cache-control: max-age=0, no-cache, no-store, must-revalidate, proxy-revalidate' -H 'authority: developer.apple.com' -H 'referer: https://developer.apple.com/account/' -H 'csrf_ts: 1552204197631' --data-binary '{}' --compressed
    """
    parsed_context = curl_parse_context(cmd)
    rsp = requests.post(
        parsed_context.url,
        data=parsed_context.data,
        headers=parsed_context.headers,
        cookies=parsed_context.cookies,
    )
    if rsp.status_code != 200:
        return {
            "succ": False,
            "reason": "无效的curl",
        }
    if parsed_context.url == "https://developer.apple.com/services-account/QH65B2/account/getUserProfile":
        data = rsp.json()
        account = data["userProfile"]["email"]
        _info = IosAccountInfo.objects.filter(account=account).first()  # type:IosAccountInfo
        _info.cookie = json_str(parsed_context.cookies)
        _info.headers = json_str(parsed_context.headers)
        _info.save()
    return {
        "succ": True,
    }


@Action
def upload_ipa(project: str, account: str, file: bytes):
    base = os.path.join("static/income", project)
    os.makedirs(base, exist_ok=True)
    _info = IosAccountInfo.objects.filter(account=account).first()  # type:IosAccountInfo
    with open(os.path.join(base, "%s_%s.ipa" % (_info.team_id, _info.devices_num)), mode="wb") as fout:
        fout.write(file)
    return {
        "succ": True,
    }


def _asset_url(path):
    return "http://127.0.0.1:8000/income/%s" % path


# noinspection PyShadowingNames
@Action
def download_ipa(uuid: str):
    _user = UserInfo.objects.filter(uuid=uuid).first()  # type: UserInfo
    _info = IosAccountInfo.objects.filter(account=_user.account).first()  # type:IosAccountInfo
    return HttpResponseRedirect(_asset_url("%s/%s_%s.ipa" % (_user.project, _info.team_id, _info.devices_num)))
