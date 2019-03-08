# -*- coding:utf-8 -*-
# 定义各种字段的默认值
import json
import os
import time
from collections import ChainMap
from math import ceil
from typing import Callable, List, Optional, Sequence, Iterable, Dict

import pymongo
import redis
from redis.client import PubSub

from base.style import Fail, ExJSONEncoder, Log, now, json_str, Assert, str_json

pool_map = {

}


# todo: 支持定制
def db_redis(index):
    host = os.environ.get("REDIS_HOST", None)
    port = os.environ.get("REDIS_PORT", 6379)
    password = os.environ.get("REDIS_AUTH", None)
    if host is None:
        # 优先走docker
        if "REDIS_PORT" in os.environ and "REDIS_PORT_6379_TCP_ADDR" in os.environ:
            host = os.environ["REDIS_PORT_6379_TCP_ADDR"]
            port = 6379
        else:
            host = "127.0.0.1"
            port = 6379
    db = redis.StrictRedis(host=host, port=port, decode_responses=True, db=index, password=password)
    # PATCH: 部分云的redis不支持select
    try:
        db.execute_command("select", "%s" % index)
    except:
        # todo: 关闭之前的
        key = "%s:%s" % (host, port)
        if pool_map.get(key, None) is None:
            pool_map[key] = redis.ConnectionPool(host=host, port=port, password=password, db=0, decode_responses=True)
        pool = pool_map[key]
        db = redis.StrictRedis(host=host, port=port, decode_responses=True, password=password, connection_pool=pool)
    return db


def session_redis(index):
    """
    暂时留用的
    """
    host = os.environ.get("SESSION_REDIS_HOST", None)
    port = os.environ.get("SESSION_REDIS_PORT", 6379)
    if host is None:
        return None
    db = redis.StrictRedis(host=host, port=port, decode_responses=True, db=index)
    db.execute_command("select", "%s" % index)
    return db


def _mongo(cate):
    host = os.environ.get("MONGO_HOST", '127.0.0.1')
    port = os.environ.get("MONGO_PORT", 27017)
    auth = os.environ.get("MONGO_AUTH", "")
    name = os.environ.get("MONGO_NAME", "model")
    if len(auth):
        auth = "%s@" % auth
    db = pymongo.MongoClient('mongodb://%s%s:%s/' % (auth, host, port),
                             socketTimeoutMS=2000,
                             connectTimeoutMS=1000,
                             serverSelectionTimeoutMS=1000,
                             connect=True,
                             )
    db.server_info()
    collection = db[name][cate]
    if "_key_1" not in collection.index_information():
        collection.create_index("_key", unique=True, sparse=True, background=True)
    return collection


def mongo_index(cate, index, unique=False):
    collection = _mongo(cate)
    if ("%s_1" % index) not in collection.index_information():
        Log("创建mongo索引[%s][%s][unique:%s]" % (cate, index, unique))
        collection.create_index(index, unique=unique, sparse=True, background=True)


__mongo_map = {}


def mongo(cate) -> pymongo.collection.Collection:
    ret = __mongo_map.get(cate)
    if ret is None:
        ret = __mongo_map[cate] = _mongo(cate)
    return ret


def mongo_pack_pop(key, model):
    _id = "%s_%s" % (model, key)
    ret = mongo(model).find_one({"_id": _id}, ["__pack__", "__length__"])
    if ret is None:
        return
    pack_length = ret.get("__length__", 0)
    mongo(model).delete_many({"_id": {"$in": [_id] + list(map(lambda i: "%s_%s" % (_id, i), range(1, pack_length)))}})


def _mongo_pack_get(key: str, model: str, pop=False) -> List:
    _id = "%s_%s" % (model, key)
    ret = mongo(model).find_one({"_id": _id})
    if ret is None:
        return []
    pack_length = ret["__length__"]
    new_value = [ret]
    for i in range(1, pack_length):
        new_value.append(mongo(model).find_one({"_id": "%s_%s_%s" % (model, key, i)}))
    return new_value


def mongo_pack_get(key: str, model: str, pop=False) -> Optional[Dict]:
    ret = _mongo_pack_get(key, model, pop=pop)
    if len(ret) == 0:
        return None
    if len(ret) == 1:
        return ret[0]
    return str_json("".join(map(lambda x: x["__value__"], ret)))


def mongo_pack_set(key: str, value: dict, model: str, size=1 * 1000 * 1000):
    """
    大于16M的插入
    以多个对象存在
    """
    db = mongo(model)
    v = json_str(value)
    if len(v) < size:
        return mongo_set(key, value, model)
    # 需要切一下
    Assert("__pack__" not in value, "数据内不能有 __pack__ 字段")
    Assert("__no__" not in value, "数据内不能有 __no__ 字段")
    Assert("__value__" not in value, "数据内不能有 __value__ 字段")
    Assert("__length__" not in value, "数据内不能有 __length__ 字段")

    pack_length = int(ceil(len(v) / size))
    new_value = list(map(lambda x: {
        "__pack__": True,
        "__no__": v,
        "__length__": pack_length,
        "__value__": v[x * size:(x + 1) * size],
    }, range(0, pack_length)))

    if mongo(model).find_one({"_id": "%s_%s" % (model, key)}, ["__pack__", "__length__"]).get("__length__", 0) > pack_length:
        # 删除旧的部分
        mongo_pack_pop(key, model)

    mongo_set(key, new_value[0], model)
    for each in new_value[1:]:
        mongo_set(key, each, model)
    return True


def mongo_set(key: str, value: dict, model: str) -> bool:
    """
    :return: 是否插入
    """
    db = mongo(model)
    if not db.find_one_and_update(
            {"_id": key},
            {"$set": value}
    ):
        db.insert_one(ChainMap({"_id": key}, value))
        return True
    return False


def mongo_get(key: str, model=None, active=True) -> Optional[Dict]:
    if model is not None:
        if not key.startswith(model + ":"):
            return None
    i = key.index(':')
    if i <= 0:
        return None
    model, _id = key[0:i], key[i + 1:]
    if active:
        if active is True:
            active = {
                "ts": now()
            }
        ret = mongo(model).find_one_and_update({"_id": key}, {"$set": {
            "__active__": active
        }})
        if ret is not None:
            ret = json.dumps(ret, separators=(',', ':'), sort_keys=True, ensure_ascii=False)
            Log("从mongodb[%s]激活[%s][%s]" % (model, key, ret))
            db_model.set(key, ret)
        return ret
    else:
        return mongo(model).find_one({"_id": _id})


def mongo_mget(key_list: Sequence[str], model: Optional[str] = None, active=True, allow_not_found=True):
    ret = []
    for each in key_list:
        tmp = mongo_get(each, model=model, active=active)
        if tmp is None:
            if not allow_not_found:
                raise Fail("就是找不到指定的对象[%s]" % each)
            else:
                continue
        ret.append(tmp)
    return ret


db_model = db_redis(1)
db_model_ex = db_redis(2)
db_stats_ex = db_redis(3)
db_other = db_redis(4)
db_config = db_redis(0)  # 作为动态配置的存储
db_online = session_redis(11) or db_redis(11)
db_daily = session_redis(12) or db_redis(12)  # 有日期前缀缓存(会根据日期自动清理最长不会保留超过7d)
db_session = session_redis(13) or db_redis(13)  # 专门给会话用的
db_mgr = db_redis(14)
db_trash = db_redis(15)


def message_from_topic(topic: PubSub, is_json=False, limit: int = 10):
    while limit >= 0:
        msg = topic.get_message()
        if msg is None:
            break
        if msg["type"] != "message":
            # 可能是刚刚连上
            continue
        if is_json:
            yield json.loads(msg["data"])
        else:
            yield msg["data"]


def model_id_list_push(key, model, head=False, max_length=100):
    if head:
        db_model_ex.lpush(key, model.id)
    else:
        db_model_ex.rpush(key, model.id)
    if max_length < model_id_list_total(key):
        if head:
            db_model_ex.rpop(key)
        else:
            db_model_ex.lpop(key)


def model_id_list_push_values(key, models: Iterable, head=False, max_length=100):
    ids = list(map(lambda x: x.id, models))
    if head:
        db_model_ex.lpush(key, *ids)
    else:
        db_model_ex.rpush(key, *ids)
    total = model_id_list_total(key)
    if max_length < total:
        cnt = total - max_length
        for _ in range(cnt):
            if head:
                db_model_ex.rpop(key)
            else:
                db_model_ex.lpop(key)


def model_id_list_total(key):
    return db_model_ex.llen(key) or 0


def model_id_list(key: str, start=0, length=100):
    ret = db_model_ex.lrange(key, start, start + length if length >= 0 else -1)
    if ret:
        return list(map(int, ret))
    else:
        return []


def db_dirty(cate, key) -> bool:
    return db_mgr.sadd("dirty:%s" % cate, key) > 0


def index_set(key: str, index: int, model_id: int):
    db_model_ex.zadd(key, model_id, index)


def mapping_get(cate, mapping, prop="_key") -> Optional[str]:
    ret = db_model_ex.get("%s:%s" % (cate, mapping))
    if ret is None:
        if prop is not None and len(prop):
            tmp = mongo(cate).find_one({prop: mapping})
            if tmp is not None:
                Log("激活索引[%s:%s]=>[%s]" % (cate, mapping, tmp["id"]))
                ret = "%s:%s" % (cate, tmp["id"])
                db_model_ex.set("%s:%s" % (cate, mapping), ret, ex=3 * 24 * 3600)
    return ret


def mapping_add(cate, mapping, model_key):
    key = "%s:%s" % (cate, mapping)
    if db_model_ex.setnx(key, model_key) == 0:
        orig = db_model_ex.get(key)
        if orig == model_key:
            return
        else:
            raise Fail("mapping出现覆盖[%s:%s] => [%s]" % (key, model_key, orig))


def index_find(key: str, model_id: int):
    return db_model_ex.zrank(key, model_id)


def index_rev_find(key: str, model_id: int):
    return db_model_ex.zrevrank(key, model_id)


def index_list(key: str, start: int = 0, length: int = -1, reverse=False):
    """
    start>0 则从低到高
    start<0 则从高到低
    """
    if start >= 0:
        if length < 0:
            ret = db_model_ex.zrange(key, start, -1)
        else:
            ret = db_model_ex.zrange(key, start, start + length - 1)
    else:
        if length < 0:
            ret = db_model_ex.zrange(key, start, -1)
        else:
            ret = db_model_ex.zrange(key, start - length + 1, start)
    if reverse:
        ret.reverse()
    return list(map(int, ret))


def db_get_json_list(key_list, allow_not_found=True, fail=True, model=None):
    return list(map(json.loads, db_get_list(key_list, allow_not_found=allow_not_found, fail=fail, model=model)))


def db_get_json(key, fail=True, model=None) -> dict:
    ret = db_get(key, default=None, fail=fail, model=model)
    if ret is not None:
        ret = json.loads(ret)
    return ret


def db_get_list(key_list: Sequence[str], allow_not_found=True, fail=True, model=None):
    if len(key_list) == 0:
        return []
    start = time.time()
    orig_ret = db_model.mget(key_list)
    cost = time.time() - start
    if cost > 0.01:
        Log("耗时的db操作[%s][%s]" % (len(key_list), key_list[:10]))
    ret = list(filter(lambda x: x is not None, orig_ret))
    if len(ret) != len(key_list):
        if model is not None:
            tmp = model + ":"
            assert len(list(filter(lambda x: not x.startswith(tmp), key_list))) == 0
        for i, k_v in enumerate(zip(key_list, orig_ret)):
            if k_v[1] is not None:
                continue
            orig_ret[i] = mongo_get(k_v[0], model=model)
        ret = list(filter(lambda x: x is not None, orig_ret))

    if len(ret) != len(key_list):
        if not allow_not_found:
            if fail:
                if isinstance(fail, bool):
                    raise Fail("少了一部分的数据")
                else:
                    raise Fail(fail)
    return ret


def db_keys(pattern: str) -> List[str]:
    return db_model.keys(pattern)


def db_get(key, default=None, fail=True, model=None) -> str:
    """
    获取一个对象
    """
    ret = db_model.get(key)
    if ret is None:
        if model is not None:
            ret = mongo_get(key, model=model)
    if ret is None:
        if default is None:
            if fail:
                if fail is True:
                    raise Fail("找不到指定的对象[%s]" % key)
                else:
                    raise Fail(fail)
        else:
            # 这里的fail必须是True
            if type(default) in {int, str, bool}:
                db_set(key, default, fail=True)
            else:
                db_set_json(key, default, fail=True)
        return default
    else:
        return ret


def db_add_random_key(key_func: Callable, value: str or int or bool, retry: int = 10, fail_msg="生成key尝试失败", duration=None) -> str:
    """
    多次生成key以达到生成不重复的key的效果
    """
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)
    key = key_func()
    if db_model.set(key, value, nx=True, ex=duration):
        return key
    while retry > 0:
        retry -= 1
        key = key_func()
        if db_model.set(key, value, nx=True, ex=duration):
            return key
    raise Fail(fail_msg)


def db_add(key, value: str or int or bool, fail=True) -> bool:
    """
    添加一个key
    """
    if db_model.set(key, value, nx=True):
        return True
    else:
        if fail:
            raise Fail("写入[%s]错误" % key)
        else:
            return False


def db_set(key, value: str or int or bool, fail=True) -> bool:
    """
    设置一个对象
    """
    if db_model.set(key, value):
        return value
    else:
        if fail:
            raise Fail("写入[%s]错误" % key)
        else:
            return False


def db_set_json(key, value, fail=True) -> bool:
    """
    设置一个对象
    """
    if db_model.set(key, json.dumps(value, ensure_ascii=False, sort_keys=True, cls=ExJSONEncoder)):
        return True
    else:
        if fail:
            raise Fail("写入[%s]错误" % key)
        else:
            return False


def db_counter(key, get_only=False) -> int:
    """
    自增用的
    """
    if get_only:
        return int(db_model_ex.incr(key, amount=0))
    else:
        return int(db_model_ex.incr(key, amount=1))


def db_incr(key):
    """
    自增用的
    """
    return db_model.incr(key, amount=1)


def db_del(key) -> bool:
    """
    删除一个对象
    :param key:
    """
    return db_model.delete(key) > 0


def db_pop(key, fail=True) -> str or None:
    """
    读取并删除
    """
    if db_model.move(key, 15):
        # 转移到回收站
        ret = db_trash.get(key)
    else:
        # 可能回收站已经有了
        # 回归原始的操作
        ret = db_model.get(key)
        if ret is None:
            if fail:
                raise Fail("找不到指定的key[%s]" % key)
            else:
                return None
        else:
            db_model.delete(key)
    if ret:
        return ret


def clean_trash():
    db_trash.flushdb()
