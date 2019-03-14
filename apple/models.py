from django.db import models


# Create your models here.

class IosAccountInfo(models.Model):
    """
    账号而已
    最高级别的原始数据
    """

    class Meta:
        db_table = "ios_account_info"

    account = models.CharField(max_length=128, primary_key=True)
    password = models.CharField(max_length=128)
    teams = models.CharField(max_length=128)
    team_id = models.CharField(max_length=128, db_index=True)
    cookie = models.TextField()
    headers = models.CharField(max_length=1024)
    csrf = models.CharField(max_length=128)
    csrf_ts = models.BigIntegerField()
    devices = models.TextField()
    devices_num = models.IntegerField()


class IosDeviceInfo(models.Model):
    """
    针对某个设备的
    """

    class Meta:
        db_table = "ios_device_info"

    udid = models.CharField(max_length=128, primary_key=True, db_column="udid", blank=False)
    device_id = models.CharField(max_length=128, db_index=True)
    model = models.CharField(max_length=128)
    sn = models.CharField(max_length=128)
    create = models.DateTimeField(auto_now=True)


class IosAppInfo(models.Model):
    """
    针对某个app的
    """

    class Meta:
        db_table = "ios_app_info"

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

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    app = models.CharField(max_length=128, db_index=True)
    cert_req_id = models.CharField(max_length=128)
    name = models.CharField(max_length=128)
    cert_id = models.CharField(max_length=128)
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

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    app = models.CharField(max_length=128, db_index=True)
    profile_id = models.CharField(max_length=128, db_index=True)
    devices = models.TextField()
    devices_num = models.IntegerField()
    expire = models.DateTimeField()
    last = models.DateTimeField(auto_now=True)
    profile = models.TextField()


class IosProjectInfo(models.Model):
    """
    针对某个工程的
    """

    class Meta:
        db_table = "ios_project_info"

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    project = models.CharField(max_length=128, db_index=True, help_text="工程名字")
    bundle_prefix = models.CharField(max_length=128, help_text="用于生成各个app用的")
    md5sum = models.CharField(max_length=128, help_text="原始ipa的md5")


class UserInfo(models.Model):
    """
    一个设备跟一个proj绑定为一个用户
    """

    class Meta:
        db_table = "user_info"

    uuid = models.CharField(max_length=128, primary_key=True, help_text="随机分配的")
    udid = models.CharField(max_length=128, db_index=True, help_text="设备id 关联IosDeviceInfo")
    project = models.CharField(max_length=128, db_index=True, help_text="对应的工程 关联IosProjectInfo")
    app = models.CharField(max_length=128, help_text="被分配的app 关联IosAppInfo")
    account = models.CharField(max_length=128, help_text="被分配的账号 关联IosAccountInfo")
    create = models.DateTimeField(auto_now=True)
