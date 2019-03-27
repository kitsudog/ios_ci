from datetime import datetime

from django.db import models

# Create your models here.
from core.models import validate_json


class IosAccountInfo(models.Model):
    """
    账号而已
    最高级别的原始数据
    """

    class Meta:
        db_table = "ios_account_info"
        verbose_name_plural = '账号'

    account = models.EmailField("账号名", max_length=128, primary_key=True)
    password = models.CharField("密码", max_length=128)
    teams = models.CharField("所有分组", max_length=128)
    team_id = models.CharField("当前分组", default="", max_length=32, db_index=True)
    team_member_id = models.CharField("组内id", default="", max_length=32, db_index=True)
    cookie = models.TextField("当前cookie", default="{}", editable=False, validators=[validate_json])
    headers = models.CharField(max_length=1024, default="{}", editable=False, validators=[validate_json])
    csrf = models.CharField(max_length=128)
    csrf_ts = models.BigIntegerField(default=0)
    devices = models.TextField("当前设备", default="{}", editable=False, validators=[validate_json])
    devices_num = models.IntegerField("设备数", default=0, editable=False)
    phone = models.CharField("绑定手机", max_length=128, blank=True, help_text="二次验证用的")


class IosDeviceInfo(models.Model):
    """
    针对某个设备的
    """

    class Meta:
        db_table = "ios_device_info"
        verbose_name_plural = '设备'

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    udid = models.CharField("设备udid", max_length=128, db_index=True, blank=False)
    account = models.CharField("所属账号", max_length=128, db_index=True, blank=False)
    device_id = models.CharField("设备id", max_length=128)
    model = models.CharField("机型", max_length=128)
    sn = models.CharField(max_length=128)
    create = models.DateTimeField("登记时间", auto_now=True)


class IosAppInfo(models.Model):
    """
    针对某个app的
    """

    class Meta:
        db_table = "ios_app_info"
        verbose_name_plural = 'App'

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    app = models.CharField(max_length=128, db_index=True)
    app_id_id = models.CharField(max_length=128, db_index=True)
    name = models.CharField(max_length=128)
    prefix = models.CharField(max_length=128)
    identifier = models.CharField(max_length=128)
    create = models.DateTimeField(auto_now=True)
    project = models.CharField(max_length=128, db_index=True, help_text="已经挂载的项目")


class IosCertInfo(models.Model):
    """
    针对某个证书的
    """

    class Meta:
        db_table = "ios_cert_info"
        verbose_name_plural = '证书'

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    account = models.CharField(max_length=128, db_index=True)
    cert_id = models.CharField(max_length=128, db_index=True)
    cert_req_id = models.CharField(max_length=128)
    name = models.CharField(max_length=128)
    sn = models.CharField(max_length=128)
    type_str = models.CharField(max_length=128)
    expire = models.DateTimeField()
    create = models.DateTimeField(auto_now=True)
    cert_p12 = models.TextField()


class IosProfileInfo(models.Model):
    """
    针对具体配置的
    """

    class Meta:
        db_table = "ios_profile_info"
        verbose_name_plural = 'MobileProfile配置'

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    app = models.CharField(max_length=128)
    profile_id = models.CharField(max_length=128)
    devices = models.TextField(default="{}")
    devices_num = models.IntegerField()
    certs = models.TextField(default="{}")
    expire = models.DateTimeField(db_index=True)
    profile = models.TextField()
    project = models.CharField(max_length=128, db_index=True)


class IosProjectInfo(models.Model):
    """
    针对某个工程的
    """

    class Meta:
        db_table = "ios_project_info"
        verbose_name_plural = '项目'

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    project = models.CharField("项目名", max_length=128, db_index=True, help_text="工程名字")
    bundle_prefix = models.CharField("bundle_id前缀", max_length=128, help_text="用于生成各个app用的")
    md5sum = models.CharField("项目md5sum", max_length=128, help_text="原始ipa的md5")
    capability = models.CharField("项目权限", max_length=1024, default='["GAME_CENTER", "IN_APP_PURCHASE"]', help_text="原始的权限")
    comments = models.CharField("备注信息", max_length=2048, default="{}", validators=[validate_json])


class UserInfo(models.Model):
    """
    一个设备跟一个proj绑定为一个用户
    """

    class Meta:
        db_table = "user_info"
        verbose_name_plural = '用户'

    uuid = models.CharField(max_length=128, primary_key=True, help_text="随机分配的")
    udid = models.CharField(max_length=128, db_index=True, help_text="设备id 关联IosDeviceInfo")
    project = models.CharField(max_length=128, db_index=True, help_text="对应的工程 关联IosProjectInfo")
    app = models.CharField(max_length=128, help_text="被分配的app 关联IosAppInfo")
    account = models.CharField(max_length=128, help_text="被分配的账号 关联IosAccountInfo")
    create = models.DateTimeField(auto_now=True)


class TaskInfo(models.Model):
    """
    每个打包的任务封装成一个任务对象
    """

    class Meta:
        db_table = "task_info"
        verbose_name_plural = '打包任务'

    uuid = models.CharField("任务id", max_length=128, primary_key=True, help_text="跟着user_info.uuid")
    state = models.CharField("状态", max_length=128, db_index=True, choices=(
        ("ready", "准备"),
        ("prepare_env", "准备环境"),
        ("prepare_cert", "下载证书"),
        ("prepare_mp", "下载mobileprofile"),
        ("prepare_ipa", "下载ipa"),
        ("unzip_ipa", "解压ipa"),
        ("resign", "重新签名"),
        ("package_ipa", "重新封包"),
        ("upload_ipa", "上传ipa"),
        ("succ", "打包成功"),
        ("none", "尚未认领"),
        ("fail", "打包失败"),
        ("expire", "打包超时"),
    ), help_text="当前任务的状态", default="ready")
    worker = models.CharField("打包终端", max_length=128, db_index=True, help_text="当前工作的打包机", default="none")
    size = models.IntegerField("包尺寸", default=0, help_text="ipa的尺寸, 打包完成后才会有")
    expire = models.DateTimeField("任务过期时间", default=datetime.now, help_text="打包任务的超时时间")
