from base.style import to_form_url


def entry(path, params=None):
    """
    能用的入口
    主要用于回调
    """
    if path[0] != "/":
        path = "/" + path
    if params is None:
        return "http://open.sklxsj.com" + path
    else:
        return "http://open.sklxsj.com" + path + "?" + to_form_url(params)
