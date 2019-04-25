import os

import gevent

from base.style import ILock, Assert, now, Fail
from frameworks.db import db_session


def valid_host(src: str):
    ret = []
    for each in src.split(","):
        host, _, port = each.rpartition(":")
        if host:
            ret.append(host)
            ret.append(each)
        else:
            ret.append(each)
    return ret


__HOST = valid_host(os.environ.get("VIRTUAL_HOST", "127.0.0.1:8000"))[0]
__STATIC_HOST = os.environ.get("STATIC_HOST", "static_%s" % __HOST)


def entry(path: str, follow_proto=False, proto="http") -> str:
    if not path.startswith("/"):
        path = "/" + path
    if follow_proto:
        return "//%s%s" % (__HOST, path)
    else:
        return "%s://%s%s" % (proto, __HOST, path)


def static_entry(path: str, follow_proto=False, proto="http") -> str:
    if not path.startswith("/"):
        path = "/" + path
    if follow_proto:
        return "//%s%s" % (__STATIC_HOST, path)
    else:
        return "%s://%s%s" % (proto, __STATIC_HOST, path)


class DbLock(ILock):
    def __init__(self, key: str, timeout=None):
        Assert(key, "key必须有效")
        self.__key = "lock:" + key
        self.__lock = False
        self.__timeout = timeout

    def acquire(self, timeout=10000, delta=10):
        timeout = self.__timeout or timeout // 1000 or 1000
        if db_session.set(self.__key, 1, ex=timeout, nx=False):
            self.__lock = True
            return
        expire = now() + timeout
        while now() < expire:
            if db_session.set(self.__key, 1, ex=timeout, nx=False):
                self.__lock = True
                return
            gevent.sleep(delta)
        raise Fail("[%s]锁竞争失败" % self.__key)

    def release(self):
        if self.__lock:
            db_session.delete(self.__key)
