# Create your views here.
import datetime
import os
import re
import tempfile
import time
from subprocess import call
from typing import Dict, Callable

import biplist
import gevent
import requests
from OpenSSL import crypto
from django.http import HttpResponseRedirect, HttpResponse, HttpRequest, HttpResponsePermanentRedirect, JsonResponse, StreamingHttpResponse

from apple.tasks import resign_ipa, print_hello
from base.helper import ipa_inspect
from base.style import str_json, Assert, json_str, Log, now, Block, Fail, Trace, tran, to_form_url, ide_debug, str_json_a
from base.utils import base64decode, md5bytes, base64, read_binary_file, random_str
from frameworks.base import Action
from frameworks.db import db_session, message_from_topic
from frameworks.utils import entry, static_entry
from helper.name_generator import GetRandomName
from .models import IosDeviceInfo, IosAppInfo, IosCertInfo, IosProfileInfo, IosAccountInfo, UserInfo, IosProjectInfo, TaskInfo
from .utils import IosAccountHelper, publish_security_code, curl_parse_context, get_capability


def _reg_app(_config: IosAccountInfo, project: str, app_id_id: str, name: str, prefix: str, identifier: str):
    sid = "%s:%s" % (_config.account, project)
    _info = IosAppInfo()
    _info.sid = sid
    _info.app = _config.account
    _info.app_id_id = app_id_id
    _info.identifier = identifier
    _info.name = name
    _info.prefix = prefix
    _info.create = now()
    _info.save()
    Log("更新app[%s][%s][%s]" % (_config.account, app_id_id, identifier))


def _reg_cert(_config: IosAccountInfo, cert_req_id, name, cert_id, sn, type_str, expire):
    sid = "%s:%s" % (_config.account, cert_id)
    _info = IosCertInfo()
    _info.sid = sid
    _info.account = _config.account
    _info.cert_req_id = cert_req_id
    _info.cert_id = cert_id
    _info.sn = sn
    _info.type_str = type_str
    _info.name = name
    _info.create = now()
    _info.expire = datetime.datetime.utcfromtimestamp(expire // 1000)
    _info.save()
    Log("更新证书[%s][%s]" % (name, cert_req_id))
    return cert_req_id


def _reg_device(account: str, device_id: str, udid: str, model: str, sn: str) -> str:
    # 需要缓存
    _info = IosDeviceInfo()
    _info.sid = "%s:%s" % (account, udid)
    _info.account = account
    _info.udid = udid
    _info.device_id = device_id
    _info.model = model
    _info.sn = sn
    _info.create = now()
    _info.save()
    Log("注册新的设备[%s][%s][%s]" % (udid, device_id, sn))
    _account = IosAccountInfo.objects.get(account=account)
    device_map = str_json(_account.devices)
    device_map[udid] = device_id
    if json_str(device_map) != _account.devices:
        _account.devices = json_str(device_map)
        _account.devices_num = len(device_map)
        _account.save()
    return udid


def _get_cert(_info: IosAccountInfo) -> IosCertInfo:
    cert = IosCertInfo.objects.filter(
        account=_info.account,
        expire__gt=datetime.datetime.utcfromtimestamp(now() // 1000),
        type_str="development",
    ).first()  # type: IosCertInfo
    if not cert:
        # todo: 生成证书
        pass
    return Assert(cert, "缺少现成的开发[iOS App Development]证书[%s]" % _info.account)


def _get_app(_config: IosAccountHelper, project: str) -> IosAppInfo:
    app = IosAppInfo.objects.filter(
        sid="%s:%s" % (_config.account, project),
    ).first()  # type: IosAppInfo
    if not app:
        _project = IosProjectInfo.objects.filter(project=project).first()  # type: IosProjectInfo
        _identifier = "%s.%s" % (_project.bundle_prefix, GetRandomName())
        _config.post(
            "验证一个app",
            "https://developer.apple.com/services-account/QH65B2/account/ios/identifiers/validateAppId.action?teamId=",
            data={
                "teamId": _config.team_id,
                "appIdName": "ci%s" % project,
                "appIdentifierString": _identifier,
                "type": "explicit",
                "explicitIdentifier": _identifier,
            },
        )
        _config.post(
            "注册一个app",
            "https://developer.apple.com/services-account/v1/bundleIds",
            data=json_str({
                "data": {
                    "type": "bundleIds",
                    "attributes": {
                        "name": "ci%s" % project,
                        "identifier": _identifier,
                        "platform": "IOS",
                        "seedId": _config.team_id,
                        "teamId": _config.team_id,
                    },
                    "relationships": {
                        "bundleIdCapabilities": {
                            "data": tran(get_capability, str_json(_project.capability)),
                        },
                    },
                },
            }),
            ex_headers={
                "content-type": "application/vnd.api+json",
            },
            csrf=True,
            json_api=False,
            status=201,
        )
        __list_all_app(_config, project)
        app = IosAppInfo.objects.filter(
            sid="%s:%s" % (_config.account, project),
        ).first()  # type: IosAppInfo
    return Assert(app, "账号[%s]缺少app[%s]" % (_config.account, project))


def __list_all_app(_config: IosAccountHelper, project: str):
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
        if not app["name"].startswith("ci"):
            continue
        if project:
            if app["name"] != "ci%s" % project:
                continue
            _reg_app(_config.info, project, app["appIdId"], app["name"], app["prefix"], app["identifier"])
        else:
            _reg_app(_config.info, app["name"][2:], app["appIdId"], app["name"], app["prefix"], app["identifier"])


def _to_ts(date_str: str):
    return int(time.mktime(time.strptime(date_str.replace("Z", "UTC"), '%Y-%m-%dT%H:%M:%S%Z')) * 1000)


def _to_dt(date_str: str):
    return datetime.datetime.utcfromtimestamp(_to_ts(date_str) // 1000)


def __download_profile(_config: IosAccountHelper, _profile: IosProfileInfo):
    ret = _config.post(
        "获取profile文件",
        "https://developer.apple.com/services-account/QH65B2/account/ios/profile/downloadProfileContent?teamId=",
        data={
            "provisioningProfileId": _profile.profile_id,
        },
        json_api=False,
        is_json=False,
        log=False,
        is_binary=True,
        method="GET",
    )
    profile = base64(ret)
    if profile != _profile.profile:
        _profile.profile = base64(ret)
        _profile.save()
        Log("更新profile文件[%s]" % _profile.sid)


def __profile_detail(_config: IosAccountHelper, _profile: IosProfileInfo):
    ret = _config.post(
        "获取profile详情",
        "https://developer.apple.com/services-account/QH65B2/account/ios/profile/getProvisioningProfile.action?teamId=",
        data={
            "includeInactiveProfiles": True,
            "provisioningProfileId": _profile.profile_id,
            "teamId": _config.team_id,
        },
    )
    profile = ret["provisioningProfile"]
    devices = list(map(lambda x: x["deviceNumber"], profile["devices"]))
    devices_str = json_str(devices)
    if _profile.devices != devices_str:
        _profile.devices = devices_str
        _profile.devices_num = len(devices)
        __download_profile(_config, _profile)
        Log("更新profile[%s]" % _profile.sid)
        _profile.save()
    certs = []
    for each in profile["certificates"]:
        certs.append(each["certificateId"])
    if _profile.certs != json_str(certs):
        _profile.certs = json_str(certs)
        _profile.save()


def __list_all_profile(_config: IosAccountHelper, target_project: str = ""):
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
    target = None
    for profile in ret["provisioningProfiles"]:
        if not profile["name"].startswith("专用 "):
            continue
        project = profile["name"].replace("专用 ", "")
        _info = IosProfileInfo.objects.filter(sid="%s:%s" % (_config.account, project)).first()  # type: IosProfileInfo
        expire = _to_dt(profile["dateExpire"])
        detail = False
        if not _info:
            _info = IosProfileInfo()
            _info.sid = "%s:%s" % (_config.account, project)
            _info.app = _config.account
            _info.profile_id = profile["provisioningProfileId"]
            _info.expire = expire
            _info.devices = ""
            _info.devices_num = 0
            detail = True

        if _info.expire != expire:
            _info.profile_id = profile["provisioningProfileId"]
            _info.expire = expire
            detail = True

        if detail:
            # 获取细节
            __profile_detail(_config, _info)
            Log("更新profile[%s]" % _info.sid)
            _info.save()
        if project == target_project:
            target = _info
    return ret, target


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
        _reg_cert(
            _config.info,
            cert["certRequestId"],
            "%s (%s)" % (cert["name"], cert["ownerId"]),
            cert["certificateId"],
            cert["serialNum"],
            cert["certificateType"]["permissionType"],
            _to_ts(cert["expirationDate"]),
        )


@Action
def init_account(account: str):
    _config = IosAccountHelper(IosAccountInfo.objects.get(account=account))
    __list_all_devices(_config)
    __list_all_app(_config, "")
    __list_all_cert(_config)
    __list_all_profile(_config)
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


def _newbee(_project: IosProjectInfo):
    # 默认一天的时效
    for _ in range(100):
        import uuid
        _uuid = uuid.uuid4()
        if db_session.set("uuid:%s" % _uuid, json_str({
            "project": _project.project,
        }), ex=3600 * 24, nx=True):
            Log("生成[%s]一个新的uuid[%s]" % (_project.project, _uuid))
            return str(_uuid)

    raise Fail("生成失败")


@Action
def newbee(project: str):
    """
    根据项目生成具体的一个可以注册新设备的uuid
    """
    _info = IosProjectInfo.objects.filter(project=project).first()  # type: IosProjectInfo
    Assert(_info is not None, "找不到对应的项目[%s]" % project)
    return {
        "uuid": _newbee(_info),
    }


def __fetch_account(udid: str, project: str, action: Callable[[IosAccountInfo, str, str], bool]) -> IosAccountInfo:
    """
    循环使用所有的账号
    """
    for each in IosAccountInfo.objects.filter(devices_num__lt=100).order_by("-devices_num"):
        if action(each, udid, project):
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
    for device_id in set(map(lambda x: x["deviceId"], ret["devices"])) - set(str_json(_config.info.devices).values()):  # type: Dict
        device = list(filter(lambda x: x["deviceId"] == device_id, ret["devices"]))[0]
        _reg_device(_config.account, device["deviceId"],
                    device["deviceNumber"],
                    device.get("model", device.get("deviceClass", "#UNKNOWN#")),
                    device.get("serialNumber", "#UNKNOWN#"))
    # 更新一下info
    devices = dict(map(lambda x: (x["deviceNumber"], x["deviceId"]), ret["devices"]))
    if json_str(devices) != _config.info.devices:
        Log("更新设备列表[%s]数量[%s]=>[%s]" % (_config.account, _config.info.devices_num, len(devices)))
        _config.info.devices = json_str(devices)
        _config.info.devices_num = len(devices)
        _config.info.save()


def __add_device(account: IosAccountInfo, udid: str, project: str) -> bool:
    title = "设备%s" % udid
    _config = IosAccountHelper(account)
    try:
        if udid not in account.devices:
            # 先注册设备
            ret = _config.post(
                "验证设备udid",
                "https://developer.apple.com/services-account/QH65B2/account/ios/device/validateDevices.action?teamId=", {
                    "deviceNames": title,
                    "deviceNumbers": udid,
                    "register": "single",
                    "teamId": _config.team_id,
                }, cache=True)
            if len(ret["failedDevices"]) == 0:
                added = False
            else:
                if "already exists on this team" in ret["failedDevices"][0]:
                    # 已经添加过了
                    Log("[%s]已经添加过的设备了[%s]" % (account.account, udid))
                    added = True
                    __list_all_devices(_config)
                else:
                    raise Fail("验证udid请求失败[%s][%s]" % (udid, ret["validationMessages"]))
            if not added:
                __list_all_devices(_config)
                ret = _config.post(
                    "添加设备",
                    "https://developer.apple.com/services-account/QH65B2/account/ios/device/addDevices.action?teamId=%s" % _config.team_id,
                    {
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
                _reg_device(_config.account, device["deviceId"], device["deviceNumber"], device["model"], device["serialNumber"])

        with Block("更新"):
            ret, _info = __list_all_profile(_config, project)
            if not _info:
                _info = IosProfileInfo()
                _info.sid = "%s:%s" % (_config.account, project)
                _info.app = _config.account
                _info.devices = "[]"
                _info.devices_num = 0
                _info.project = project

            devices = str_json_a(_info.devices)

            if udid in devices:
                pass
            else:
                devices.append(udid)
                with Block("默认全开当期的设备"):
                    # noinspection PyTypeChecker
                    devices = list(set(devices + list(str_json(_config.info.devices).keys())))
                _cert = _get_cert(_config.info)
                _app = _get_app(_config, project)
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
                            "deviceIds": ",".join(map(lambda x: str_json(_config.info.devices)[x], devices)),
                        }, csrf=True)
                    Assert(ret["resultCode"] == 0)
                    _info.devices = json_str(devices)
                    _info.profile_id = each["provisioningProfileId"]
                    # noinspection PyTypeChecker
                    _info.profile = ret["provisioningProfile"]["encodedProfile"]
                    _info.expire = _to_dt(ret["provisioningProfile"]["dateExpire"])
                    _info.save()
                    found = True
                    Log("更新证书[%s]添加设备[%s][%s]成功" % (project, udid, len(devices)))
                    break
                if not found:
                    ret = _config.post(
                        "创建ProvisioningProfile",
                        "https://developer.apple.com/services-account/QH65B2/account/ios/profile/createProvisioningProfile.action?teamId=",
                        data={
                            "subPlatform": "",
                            "certificateIds": _cert.cert_req_id,
                            "deviceIds": ",".join(map(lambda x: str_json(_config.info.devices)[x], devices)),
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
                    _info.expire = _to_dt(ret["provisioningProfile"]["dateExpire"])
                    _info.save()
                    Log("添加证书[%s]添加设备[%s][%s]成功" % (project, udid, len(devices)))
    except Exception as e:
        Trace("添加设备出错了[%s]" % e, e)
        return False
    return True


def __add_task(title: str, _user: UserInfo, force=False):
    _account = IosAccountInfo.objects.get(account=_user.account)
    _project = IosProjectInfo.objects.get(project=_user.project)
    _profile = IosProfileInfo.objects.get(sid="%s:%s" % (_user.account, _user.project))
    if not str_json_a(_profile.certs):
        __profile_detail(_account, _profile)
    _cert = IosCertInfo.objects.get(sid="%s:%s" % (_user.account, str_json_a(_profile.certs)[0]))
    Assert(_profile, "[%s][%s]证书无效" % (_project.project, _account.account))
    Assert(_project.md5sum, "项目[%s]原始ipa还没上传" % _project.project)
    Assert(_cert.cert_p12, "项目[%s]p12还没上传" % _project.project)
    if not force:
        # 是否可以跳过
        devices = str_json_a(_profile.devices)
        if _user.udid in devices:
            filepath = "income/%s/%s_%s.ipa" % (_user.project, _account.team_id, _account.devices_num)
            if os.path.exists(filepath):
                Log("[%s][%s]已经有包了跳过打包" % (_user.project, _user.uuid))
                _task, _ = TaskInfo.objects.get_or_create(uuid=_user.uuid)
                _task.state = "succ"
                _task.worker = "-"
                _task.expire = 0
                _task.save()
                return
    _task, _ = TaskInfo.objects.get_or_create(uuid=_user.uuid)
    _task.state = "none"
    _task.worker = ""
    _task.expire = datetime.datetime.utcfromtimestamp((now() + 60 * 1000) // 1000)
    _task.save()
    Log("[%s]发布任务[%s][%s][%s]" % (_user.project, _user.account, title, _user.udid))

    def func():
        resign_ipa.delay(**{
            "uuid": _user.uuid,
            "cert": "iPhone Developer: %s" % _cert.name,
            "cert_url": entry("/apple/download_cert?uuid=%s" % _user.uuid),
            "cert_md5": md5bytes(base64decode(_cert.cert_p12)),
            "mp_url": entry("/apple/download_mp?uuid=%s" % _user.uuid),
            "mp_md5": md5bytes(base64decode(_profile.profile)),
            "project": _project.project,
            "ipa_url": entry("/projects/%s/orig.ipa" % _user.project),
            "ipa_md5": _project.md5sum,
            "ipa_new": "%s_%s.ipa" % (_account.team_id, _account.devices_num),
            "upload_url": entry("/apple/upload_ipa?uuid=%s" % _user.uuid),
            "process_url": entry("/apple/task_state?uuid=%s" % _user.uuid),
        })

    if ide_debug():
        gevent.spawn(func)
    else:
        func()


ffi = None


# noinspection PyProtectedMember,PyBroadException
def __process_signed_plist(data: bytes) -> Dict:
    try:
        global ffi
        if not ffi:
            from cffi import FFI

            ffi = FFI()
        p7 = crypto.load_pkcs7_data(crypto.FILETYPE_ASN1, data)
        out = crypto._new_mem_buf()
        if crypto._lib.PKCS7_verify(p7._pkcs7, ffi.NULL, ffi.NULL, ffi.NULL, out, crypto._lib.PKCS7_NOVERIFY):
            return biplist.readPlistFromString(crypto._bio_to_string(out))
    except:
        try:
            return {
                "UDID": re.compile(b"<key>UDID</key>\n?\s*<string>(.+?)</string>").findall(data)[0].decode("utf8")
            }
        except:
            raise Fail("无法解读plist[%s]" % data)


# noinspection PyShadowingNames
@Action
def add_device(_content: bytes, uuid: str, udid: str = ""):
    _key = "uuid:%s" % uuid
    _detail = str_json(db_session.get(_key) or "{}")
    _account = _detail.get("account")
    if not _detail:
        raise Fail("无效的uuid[%s]" % uuid)
    project = _detail["project"]
    if not udid:
        # todo: 验证来源
        with Block("提取udid", fail=False):
            udid = __process_signed_plist(_content)["UDID"]
    if not udid:
        # 提取udid失败后删除uuid
        if ide_debug():
            pass
        else:
            db_session.delete(_key)
        return {
            "succ": False,
        }
    for _user in UserInfo.objects.filter(udid=udid, project=project):
        _account = _user.account
        if uuid != _user.uuid:
            Log("转移设备的[%s]的uuid[%s]=>[%s]" % (udid, uuid, _user.uuid))
            uuid = _user.uuid
            break

    if not _account:
        Log("为设备[%s]分配账号" % udid)
        _account = __fetch_account(udid, project, __add_device)
    else:
        _account = IosAccountInfo.objects.filter(account=_account).first()

    _user = UserInfo(uuid=uuid)
    _user.udid = udid
    _user.project = _detail["project"]
    _user.account = _account.account
    _user.save()
    __add_task("新客户端启动任务", _user)
    return HttpResponsePermanentRedirect(entry("/detail.php?project=%s&uuid=%s" % (project, uuid)))


@Action
def login_by_fastlane(_req: HttpRequest, cmd: str = "", account: str = ""):
    """
    通过命令获取会话
    fastlane spaceauth -u kitsudo163@163.com
    ex.
    export FASTLANE_SESSION='---\n- !ruby/object:HTTP::Cookie\n  name: myacinfo\n  value: DAWTKNV2e32a0823580640561dc9dfd382265048c32c2aa5b04485930b2ada1d1c7eba28dee6c6065c749f708f2a429f8f9f2d0f2f7d2ad629652ca5bc3383c0772d51c6ca34a2f7b09141f7b19c358c2b25d0738079ab1e48a06610228a574342c84ef13349ede1a012c25155e265a17989a3b09631dd953954505153fb7ef71aecfe303530cb684c89e8402cb82d8d4d93c3fc3c1209e334f65f71c7ae0cfdf0349ec757abcb104a591f5bea25ac0f1207004c19645b80ed82fb5cd0d3a740224b2f3aef9e91b049bb63a94ae3c76d027411f077069865209d733617a7a84f54cf7e9488e9b4f0a918d29f184f5ec76d95b5f55def61682f70b7f10fc12dc43d6e380213dd1f702a4f3ccab3ad438cd0f6a87c295e028a12ec410aa3fa689210d040377995914d4d3718b90f85ad5452d5db47ef9ae11c6b3216cf8ab61025adc203b0bf072ce832240c384d83f0f4aaf477a3c7313de4c20c5e32c530ff1ad76aebcd8538ac485a9a46941dfa94ee2f3fb40e38666533326562333665333834343461323366383636666563303166613533303330656361323836MVRYV2\n  domain: apple.com\n  for_domain: true\n  path: "/"\n  secure: true\n  httponly: true\n  expires: \n  max_age: \n  created_at: 2019-03-15 11:55:51.031441000 +08:00\n  accessed_at: 2019-03-15 11:55:51.041509000 +08:00\n- !ruby/object:HTTP::Cookie\n  name: dqsid\n  value: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJzZnp2ZGFldGJPeWpXaTc1LVpTRmNBIn0.IEYqXF-pxIYdIwP2rdNRNhoxdCzJgGxt4olTZa2fXo8\n  domain: olympus.itunes.apple.com\n  for_domain: false\n  path: "/"\n  secure: true\n  httponly: true\n  expires: \n  max_age: 1800\n  created_at: &1 2019-03-15 11:55:52.798977000 +08:00\n  accessed_at: *1\n
    curl localhost:8000/apple/login_by_fastlane --data $FASTLANE_SESSION
    """
    if not cmd:
        cmd = _req.body.decode("utf-8")
    Assert(len(cmd), "命令行不对")
    cmd = cmd.replace("\\n", "")
    cookie = dict(re.compile(r"name:\s+(\S+)\s+value:\s+(\S+)").findall(cmd))
    if not account:
        rsp = requests.post("https://developer.apple.com/services-account/QH65B2/account/getUserProfile", headers={
            "cookie": to_form_url(cookie, split=';')
        })
        if rsp.status_code != 200:
            return {
                "succ": False,
                "reason": "无效的fastlane export",
            }
        data = rsp.json()
        account = data["userProfile"]["email"]

    if account:
        _info = IosAccountInfo.objects.filter(account=account).first()  # type:IosAccountInfo
        if not _info:
            _info = IosAccountInfo()
            _info.account = account
            _info.save()
        _info.cookie = json_str(cookie)
        _info.headers = json_str({})
        _info.save()
        Log("通过fastlane登录[%s]" % account)
        return {
            "succ": True,
            "msg": "登录[%s]成功" % account,
        }
    else:
        return {
            "succ": False,
            "msg": "请求不具备提取登录信息",
        }


@Action
def login_by_curl(_req: HttpRequest, cmd: str = "", account: str = ""):
    """
    通过拦截网页的curl 请求
    https://developer.apple.com/account
    ex.
    curl 'https://developer.apple.com/services-account/QH65B2/account/getUserProfile' -H 'origin: https://developer.apple.com' -H 'accept-encoding: gzip, deflate, br' -H 'accept-language: zh-CN,zh;q=0.9' -H 'csrf: cf0796aee015fe0f03e7ccc656ba4b898b696cc1072027988d89b1f6e607fd67' -H 'cookie: geo=SG; ccl=SR+vWVA/vYTrzR1LkZE2tw==; s_fid=56EE3E795513A2B4-16F81B5466B36881; s_cc=true; s_vi=[CS]v1|2E425B0B852E2C90-40002C5160000006[CE]; dslang=CN-ZH; site=CHN; s_pathLength=developer%3D2%2C; acn01=v+zxzKnMyleYWzjWuNuW1Y9+kAJBxfozY2UAH0paNQB+FA==; myacinfo=DAWTKNV2a5c238e8d27e8ed221c8978cfb02ea94b22777f25ffec5abb1a855da8debe4f59d60b506eae457dec4670d5ca9663ed72c3d1976a9f87c53653fae7c63699abe64991180d7c107c50ce88be233047fc96de200c3f23947bfbf2e064c7b9a7652002d285127345fe15adf53bab3d347704cbc0a8b856338680722e5d0387a5eb763d258cf19b79318be28c4abd01e27029d2ef26a1bd0dff61d141380a1b496b92825575735d0be3dd02a934db2d788c9d6532b6a36bc69d244cc9b4873cef8f4a3a90695f172f6f521330f67f20791fd7d62dfc9d6de43899ec26a8485191d62e2c5139f81fca2388d57374ff31f9f689ad373508bcd74975ddd3d3b7875fe3235323962636433633833653433363562313034383164333833643736393763303538353038396439MVRYV2; DSESSIONID=1c3smahkpfbkp7k3fju30279uoba8p8480gs5ajjgsbbvn8lubqt; s_sq=%5B%5BB%5D%5D' -H 'user-locale: en_US' -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.81 Safari/537.36 QQBrowser/4.5.122.400' -H 'content-type: application/json' -H 'accept: application/json' -H 'cache-control: max-age=0, no-cache, no-store, must-revalidate, proxy-revalidate' -H 'authority: developer.apple.com' -H 'referer: https://developer.apple.com/account/' -H 'csrf_ts: 1552204197631' --data-binary '{}' --compressed
    """

    if not cmd:
        cmd = _req.body.decode("utf-8")
    Assert(len(cmd) and cmd.startswith("curl"), "命令行不对")
    parsed_context = curl_parse_context(cmd)
    params = {
        "data": parsed_context.data,
        "headers": dict(filter(lambda x: not x[0].startswith(":"), parsed_context.headers.items())),
        "cookies": parsed_context.cookies,
    }
    if parsed_context.method == 'get':
        rsp = requests.get(
            parsed_context.url,
            **params,
        )
    else:
        rsp = requests.post(
            parsed_context.url,
            **params,
        )
    if rsp.status_code != 200:
        return {
            "succ": False,
            "reason": "无效的curl",
        }
    if parsed_context.url == "https://developer.apple.com/services-account/QH65B2/account/getUserProfile":
        data = rsp.json()
        account = data["userProfile"]["email"]
    else:
        rsp = requests.post("https://developer.apple.com/services-account/QH65B2/account/getUserProfile", cookies=parsed_context.cookies)
        data = rsp.json()
        account = data["userProfile"]["email"]

    if account:
        _info = IosAccountInfo.objects.filter(account=account).first()  # type:IosAccountInfo
        if not _info:
            _info = IosAccountInfo()
            _info.account = account
            _info.save()
        _info.cookie = json_str(parsed_context.cookies)
        _info.headers = json_str(parsed_context.headers)
        _info.save()
        Log("通过curl登录[%s]" % account)
        return {
            "succ": True,
            "msg": "登录[%s]成功" % account,
        }
    else:
        return {
            "succ": False,
            "msg": "请求不具备提取登录信息",
        }


@Action
def upload_project_ipa(project: str, file: bytes):
    _project = IosProjectInfo.objects.get(project=project)
    base = os.path.join("static/projects", project)
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, "orig.ipa"), mode="wb") as fout:
        fout.write(file)
    if _project.md5sum != md5bytes(file):
        _project.md5sum = md5bytes(file)
        _project.save()
        Log("更新工程[%s]的ipa[%s]" % (project, _project.md5sum))
    with Block("提取app信息"):
        _info = ipa_inspect.info(file)
        comments = str_json(_project.comments)
        with Block("导出图标", fail=False):
            if _info.icon:
                with open(os.path.join("income", project, "icon.png"), mode="wb") as fout:
                    fout.write(_info.icon[-1])
            comments.update({
                "icon": static_entry("income/%s/icon.png" % project),
            })
        comments.update({
            "name": _info.name,
            "version": _info.CFBundleVersion,
        })
        if json_str(comments) != _project.comments:
            Log("更新项目的详情[%s][%s]=>[%s]" % (project, _project.comments, json_str(comments)))
            _project.comments = json_str(comments)
            _project.save()

    # todo: 激活更新一下
    return {
        "succ": True,
    }


@Action
def upload_cert_p12(account: str, file: bytes, password: str = "q1w2e3r4"):
    p12 = crypto.load_pkcs12(file, password)
    components = p12.get_certificate().get_issuer().get_components()
    if b"Apple Worldwide Developer Relations Certification Authority" not in list(map(lambda x: x[-1], components)):
        Log("一个机构不确定的证书[%s]" % components)
        return {
            "succ": False,
            "msg": "机构未知",
        }

    tmp = re.match(r"iPhone Developer: (.+ \([A-Z0-9]+\))", p12.get_friendlyname().decode("utf8")).groups()
    Assert(len(tmp), "非法的p12文件")
    name = tmp[0]  # type: str
    _cert = IosCertInfo.objects.get(account=account, name=name)
    _cert.cert_p12 = base64(file)
    _cert.save()
    return {
        "succ": True,
    }


@Action
def upload_ipa(worker: str, uuid: str, file: bytes):
    """
    上传打好的包
    """
    _user = UserInfo.objects.get(uuid=uuid)
    project = _user.project
    account = _user.account
    base = os.path.join("static/income", project)
    os.makedirs(base, exist_ok=True)
    _info = IosAccountInfo.objects.filter(account=account).first()  # type:IosAccountInfo
    Assert(_info, "账号[%s]不存在" % account)
    md5 = md5bytes(file)
    filename = "%s_%s.ipa" % (_info.team_id, _info.devices_num)
    with open(os.path.join(base, filename), mode="wb") as fout:
        fout.write(file)

    Log("[%s]收到新打包的ipa[%s][%s]" % (account, filename, md5))
    # todo: 遍历所有的设备关联的包?
    _task, _ = TaskInfo.objects.get_or_create(uuid=uuid)
    if _task.worker in {worker, "none"}:
        _task.state = "succ"
        _task.worker = worker
        _task.size = len(file)
        _task.save()
    return {
        "succ": True,
    }


__download_file = {

}

__download_total = {

}

__download_process = {

}


# noinspection PyShadowingNames
@Action
def download_ipa(uuid: str, redirect: bool = False, download_id: str = ""):
    _user = UserInfo.objects.get(uuid=uuid)
    _info = IosAccountInfo.objects.get(account=_user.account)

    filepath = "income/%s/%s_%s.ipa" % (_user.project, _info.team_id, _info.devices_num)
    if redirect:
        return HttpResponseRedirect(static_entry(filepath))
    else:
        if not download_id:
            download_id = random_str(32)
        __download_process[download_id] = 0
        __download_total[download_id] = os.path.getsize(os.path.join("static", filepath))

        def file_iterator(chunk_size=4 * 1024):
            with open(os.path.join("static", filepath), mode="rb") as fin:
                num = 0
                while True:
                    # todo: 不允许相同的多个下载任务

                    c = fin.read(chunk_size)
                    num += len(c)
                    __download_process[download_id] = num
                    if c:
                        yield c
                    else:
                        break

        rsp = StreamingHttpResponse(file_iterator())
        rsp.set_signed_cookie("download_id", download_id, salt="zhihu")
        return rsp


@Action
def manifest(uuid: str, need_process=True, download_id: str = ""):
    _user = UserInfo.objects.get(uuid=uuid)
    _account = IosAccountInfo.objects.get(account=_user.account)
    _project = IosProjectInfo.objects.get(project=_user.project)
    _app = IosAppInfo.objects.get(sid="%s:%s" % (_user.account, _user.project))
    _comments = str_json(_project.comments)
    __download_file[download_id] = os.path.join("income", _project.project, "%s_%s.ipa" % (_account.team_id, _account.devices_num))

    if os.environ.get("FORCE_CDN", "FALSE") == "TRUE":
        need_process = False

    content = """\
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
    <dict>
        <key>items</key>
        <array>
            <dict>
                <key>assets</key>
                <array>
                    <dict>
                        <key>kind</key>
                        <string>software-package</string>
                        <key>url</key>
                        <string>%(url)s</string>
                    </dict>
                    <dict>
                        <key>kind</key>
                        <string>display-image</string>
                        <key>url</key>
                        <string>%(icon)s</string>
                    </dict>
                    <dict>
                        <key>kind</key>
                        <string>full-size-image</string>
                        <key>url</key>
                        <string>%(icon)s</string>
                    </dict>
                </array>
                <key>metadata</key>
                <dict>
                    <key>bundle-identifier</key>
                    <string>%(app)s</string>
                    <key>bundle-version</key>
                    <string>%(version)s</string>
                    <key>kind</key>
                    <string>software</string>
                    <key>title</key>
                    <string>%(title)s</string>
                </dict>
            </dict>
        </array>
    </dict>
</plist>
""" % {
        "url": static_entry("/income/%s/%s_%s.ipa") % (_project.project, _account.team_id, _account.devices_num)
        if not need_process else entry("/apple/download_ipa/uuid/%s/download_id/%s" % (uuid, download_id or random_str())),
        "uuid": uuid,
        "title": _comments["name"],
        "icon": _comments["icon"],
        "app": _app.identifier,
        "version": "1.0.0",
    }
    response = HttpResponse(content)
    response['Content-Type'] = 'application/octet-stream; charset=utf-8'
    response["Content-Disposition"] = 'attachment; filename="app.plist"'

    return response


@Action
def download_cert(uuid: str, filename: str = "cert.p12"):
    _user = UserInfo.objects.get(uuid=uuid)
    _profile = IosProfileInfo.objects.get(sid="%s:%s" % (_user.account, _user.project))
    _cert = IosCertInfo.objects.get(sid="%s:%s" % (_user.account, str_json_a(_profile.certs)[0]))
    Assert(_cert.cert_p12, "[%s]请先上传p12文件" % _user.account)
    response = HttpResponse(base64decode(_cert.cert_p12))
    response['Content-Type'] = 'application/octet-stream'
    response['Content-Disposition'] = 'attachment;filename="%s"' % filename
    return response


@Action
def download_mp(uuid: str, filename: str = "package.mobileprovision"):
    _user = UserInfo.objects.filter(uuid=uuid).first()  # type: UserInfo
    _info = IosAccountInfo.objects.filter(account=_user.account).first()  # type:IosAccountInfo
    _profile = IosProfileInfo.objects.filter(sid="%s:%s" % (_user.account, _user.project)).first()  # type:IosProfileInfo
    response = HttpResponse(base64decode(_profile.profile))
    response['Content-Type'] = 'application/octet-stream'
    response['Content-Disposition'] = 'attachment;filename="%s"' % filename
    return response


# noinspection SpellCheckingInspection
@Action
def mobconf(uuid: str = ""):
    """
    下载config实现udid的上传
    """
    if uuid:
        _url = entry("/apple/add_device?uuid=%s" % uuid, proto="https")
        orig = read_binary_file("mdmtools/mdm.mobileconfig").replace(b"#url#", _url.encode("utf8"))
        _, in_path = tempfile.mkstemp()
        _, out_path = tempfile.mkstemp()
        try:
            # todo: 缓存uuid的mobileconfig文件
            with open(in_path, mode="wb") as fout:
                fout.write(orig)
            assert call(
                ["openssl", "smime", "-sign", "-in", in_path, "-out", out_path, "-signer", "mdmtools/mobconf/InnovCertificates.pem",
                 "-inkey",
                 "mdmtools/mobconf/key.pem", "-certfile", "mdmtools/mobconf/root.crt.pem", "-outform", "der", "-nodetach", "-passin",
                 "pass:123123"], timeout=10) == 0
            rsp = HttpResponse(read_binary_file(out_path))
            rsp["Content-Type"] = "application/x-apple-aspen-config; charset=utf-8"
            rsp["Content-Disposition"] = 'attachment; filename="ioshelper.mobileconfig"'
            return rsp
        finally:
            os.remove(in_path)
            os.remove(out_path)
    else:
        # 走固定的安装之后确认uuid
        orig = read_binary_file("mdmtools/mdm_signed.mobileconfig")
        rsp = HttpResponse(orig)
        rsp["Content-Type"] = "application/x-apple-aspen-config; charset=utf-8"
        rsp["Content-Disposition"] = 'attachment; filename="ioshelper.mobileconfig"'
        return rsp


@Action
def wait():
    __pub = db_session.pubsub()
    __pub.subscribe("account:security:code")
    expire = now() + 1200 * 1000
    while now() < expire:
        gevent.sleep(1)
        for data in message_from_topic(__pub, is_json=True, limit=1):
            return data
    raise Fail("超时")


@Action
def info(_req: HttpRequest, project: str, uuid: str = ""):
    _project = IosProjectInfo.objects.filter(project=project).first()  # type: IosProjectInfo
    udid = ""
    if not _project:
        return {

        }
    ret = str_json(_project.comments)
    ready = False

    if uuid:
        _user = UserInfo.objects.filter(uuid=uuid).first()  # type: UserInfo
        if _user:
            ready = True
            udid = _user.udid
        else:
            Log("上传的uuid无效[%s]" % uuid)
    else:
        uuid = _req.get_signed_cookie("uuid", "", salt="zhihu")
        _user = UserInfo.objects.filter(uuid=uuid).first()  # type: UserInfo
        if _user:
            ready = True
            udid = _user.udid
        else:
            Log("cookie中的uuid无效[%s]" % uuid)

    if ready:
        ret.update({
            "ready": True,
        })
        _task = TaskInfo.objects.filter(uuid=uuid).first()  # type:TaskInfo
        if _task:
            if _task.state == "fail" or _task.expire.timestamp() * 1000 < now():
                __add_task("客户端重启任务", _user)

    else:
        uuid = _newbee(_project)
        ret.update({
            "ready": False,
        })

    ret.update({
        "uuid": uuid,
        "download_id": random_str(32),
    })
    rsp = JsonResponse({
        "ret": 0,
        "result": ret,
    })
    rsp.set_signed_cookie("uuid", uuid, salt="zhihu", expires=3600 * 24)
    if udid:
        rsp.set_signed_cookie("udid", _user.udid, salt="zhihu", expires=300 * 3600 * 24)
    return rsp


@Action
def get_ci():
    pass


@Action
def security_code_sms(phone: str, sms: str):
    Assert("apple" in sms.lower(), "短信非验证码短信[%s]" % sms)
    code = re.compile(r"\d{4,6}").findall(sms)
    Assert(len(code), "短信非验证码短信[%s]" % sms)
    code = code[0]
    _account = IosAccountInfo.objects.filter(phone=phone).first()  # type: IosAccountInfo
    publish_security_code(_account.account if _account else "*", code, now())
    return {
        "succ": True,
    }


@Action
def security_code(account: str, code: str):
    publish_security_code(account, code, now())
    return {
        "succ": True,
    }


_states = ["ready", "prepare_env", "prepare_cert", "prepare_mp", "prepare_ipa", "unzip_ipa", "resign", "package_ipa", "upload_ipa", "succ"]


@Action
def rebuild(uuid: str):
    _user = UserInfo.objects.get(uuid=uuid)
    __add_task("管理后台重启", _user, force=True)
    return {
        "succ": True,
    }


@Action
def task_state(uuid: str, worker: str = "", state: str = "", auto_start=True):
    _task, _ = TaskInfo.objects.get_or_create(uuid=uuid)
    if state:
        if _task.worker:
            Assert(_task.worker == worker, "越权更改任务[%s]状态[%s]=>[%s]" % (uuid, _task.worker, worker))
        else:
            _task.worker = worker
            _task.save()
        if _task.state != state:
            Log("任务[%s]状态变更[%s]=>[%s]" % (uuid, _task.state, state))
            _task.state = state
            _task.save()
        return {
            "succ": True,
        }
    else:
        if auto_start and _task.state in {"fail", "expire", "none", ""}:
            # noinspection PyTypeChecker
            rebuild({
                "uuid": uuid,
            })
        # 获取当前的状态
        return {
            "code": 1 if _task.state in {"fail", "expire"} else 0,
            "finished": _task.state == "succ",
            "progress": "%d%%" % ((_states.index(_task.state) + 1) * 100 / len(_states)) if _task.state in _states else "0%",
        }


@Action
def test():
    print_hello.delay()


@Action
def download_process(_req: HttpRequest, download_id: str, timeout=3000, last: int = 0, start: int = 0):
    if os.environ.get("FORCE_CDN"):
        if download_id not in __download_total:
            if download_id in __download_file and os.path.exists(__download_file[download_id]):
                # todo: 需要考虑断点上传
                gevent.sleep(timeout / 1000)
                __download_total[download_id] = os.path.getsize(__download_file[download_id])
            else:
                gevent.sleep(timeout / 1000)
            return {
                "code": 0,
                "progress": 0,
                "total": 1,
            }
        else:
            # 假设速度为 500k/s
            total = __download_total[download_id]
            return {
                "code": 0,
                "progress": min(total, int(500000 * (now() - start) / 1000.0)),
                "total": total,
            }
    else:
        if download_id not in __download_process:
            gevent.sleep(timeout / 1000)
            return {
                "code": 0,
                "progress": 0,
                "total": 1,
            }
        else:
            orig = last or __download_process[download_id]
            total = __download_total[download_id]
            if orig == total:
                return {
                    "code": 0,
                    "progress": total,
                    "total": total,
                }
            expire = (now() + timeout) if timeout > 0 else (now() + 30 * 1000)
            while now() < expire:
                if __download_process[download_id] == orig:
                    gevent.sleep(1)
                else:
                    # 进度有变化就马上回去
                    break
            return {
                "code": 0,
                "progress": __download_process[download_id],
                "total": total,
            }


if ide_debug():
    # noinspection PyProtectedMember
    def _debug():
        _info, created = IosProjectInfo.objects.get_or_create(sid="test", project="test")
        if created:
            Log("初始化一个测试项目")
            _info.bundle_prefix = "com.test"
            _info.save()
        upload_project_ipa._orig_func("test", read_binary_file("projects/test.ipa"))


    _debug()
