import os


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
__STATIC_HOST = "static_%s" % __HOST


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
