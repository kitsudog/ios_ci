from django.db import models


class CreateField:
    create = models.DateTimeField(auto_now_add=True)


class StrId:
    sid = models.CharField(max_length=128, primary_key=True, db_column='sid')


class IntId:
    id = models.BigAutoField(primary_key=True, db_column='id')

# # Create your models here.
# class OrderNode(StrIdNode, CreateField):
#     status = models.CharField(max_length=32)
#     platform = models.CharField(max_length=255)
#     title = models.CharField(max_length=255)
#     price = models.IntegerField()
#     pay_type = models.CharField(max_length=255)
#     # 数据装不下不够自己补
#     content = models.CharField(max_length=1024)
