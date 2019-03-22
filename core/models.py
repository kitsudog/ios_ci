from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from base.style import str_json


class CreateField:
    create = models.DateTimeField(auto_now_add=True)


class StrId:
    sid = models.CharField(max_length=128, primary_key=True, db_column='sid')


class IntId:
    id = models.BigAutoField(primary_key=True, db_column='id')


def validate_json(value: str):
    try:
        str_json(value)
    except ValueError:
        raise ValidationError(_('不合法的json字符串'), code='invalid')

# # Create your models here.
# class OrderNode(StrIdNode, CreateField):
#     status = models.CharField(max_length=32)
#     platform = models.CharField(max_length=255)
#     title = models.CharField(max_length=255)
#     price = models.IntegerField()
#     pay_type = models.CharField(max_length=255)
#     # 数据装不下不够自己补
#     content = models.CharField(max_length=1024)
