from django.db import models


# Create your models here.

class IosDeviceInfo(models.Model):
    class Meta:
        db_table = "ios_device_info"

    udid = models.CharField(max_length=128, primary_key=True, db_column="udid", blank=False)
    device_id = models.CharField(max_length=128, db_index=True)
    model = models.CharField(max_length=128)
    sn = models.CharField(max_length=128)
    create = models.DateTimeField(auto_now=True)


class IosAppInfo(models.Model):
    class Meta:
        db_table = "ios_app_info"

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    app = models.CharField(max_length=128, db_index=True)
    app_id_id = models.CharField(max_length=128, db_index=True)
    name = models.CharField(max_length=128)
    prefix = models.CharField(max_length=128)
    identifier = models.CharField(max_length=128)

    create = models.DateTimeField(auto_now=True)


class IosCertInfo(models.Model):
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


class IosProfileInfo(models.Model):
    class Meta:
        db_table = "ios_profile_info"

    sid = models.CharField(max_length=128, primary_key=True, db_column="sid", blank=False)
    app = models.CharField(max_length=128, db_index=True)
    profile_id = models.CharField(max_length=128, db_index=True)
    devices = models.CharField(max_length=2048)
    last = models.DateTimeField(auto_now=True)
    profile = models.TextField()
