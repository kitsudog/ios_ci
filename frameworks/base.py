import inspect
from abc import abstractmethod
from typing import Tuple, List, Mapping, Type, Dict, Callable

from django.http import HttpResponse, HttpRequest

from base.style import Fail, json_str
from base.utils import str_to_bool


def get_data(value: str, hint_type: Type, default_value: any = None) -> any:
    if hint_type is bool:
        return str_to_bool(value)
    elif hint_type is int:
        return int(value)
    return value


NONE = {}


def inject_params(_args, defaults, annotations) -> Tuple[Mapping[str, any], List[Tuple[str, any]]]:
    # todo: 通过annotations获取更加便捷的写法

    if defaults is None:
        # 全部默认为str
        defaults = [NONE] * len(_args)
    else:
        # 前置的补齐
        defaults = [NONE] * (len(_args) - len(defaults)) + list(defaults)
    # 基于python3 的typing进行补全
    hint_list = []
    defaults_map = {}
    for i, each in enumerate(_args):
        if defaults[i] is NONE:
            hint_list.append(annotations.get(each, str))
        else:
            if defaults[i] is None:
                defaults_map[each] = None
                hint_list.append(str)
            else:
                if type(defaults[i]) in {str, int, bool}:
                    defaults_map[each] = defaults[i]
                hint_list.append(defaults[i])
    return defaults_map, list(zip(_args, hint_list))


def to_simple_str_dict(orig: Mapping[str, List[str]]) -> Dict[str, str]:
    ret = {}
    for k, v in orig.items():
        if isinstance(v, str):
            ret[k] = v
        else:
            ret[k] = v[0]
    return ret


def to_response(ret: any, req: HttpRequest = None) -> HttpResponse:
    if isinstance(ret, HttpResponse):
        return ret
    if isinstance(ret, Mapping):
        pass
    elif callable(ret) and hasattr(ret, "_is_action"):
        assert req is not None
        depth = getattr(req, "_depth", 0) + 1
        assert depth < 10
        setattr(req, "_depth", depth)
        return to_response(ret(req))
    else:
        ret = {
            "msg": ret
        }
    rsp = HttpResponse(json_str({
        "ret": 0,
        "result": ret
    }), content_type="application/json")
    rsp["Access-Control-Allow-Origin"] = "*"
    rsp["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return rsp


# noinspection PyPep8Naming
def Action(func):
    # todo: 反射处理
    spec = inspect.getfullargspec(func)
    default_params, params_hints = inject_params(spec.args, spec.defaults, spec.annotations)
    params_key = list(zip(*params_hints))
    params_key = params_key[0] if len(params_key) else []
    req_inject_func = []  # type:List[Callable[[HttpRequest],Dict]]
    inject_func = []  # type:List[Callable[[Dict],Any]]
    last_inject_func = []  # type:List[Callable[[Dict],Any]]
    if "_ip" in params_key:
        def _func(req: HttpRequest, params: Dict):
            if "HTTP_X_FORWARDED_FOR" in req.META:
                ip = req.META['HTTP_X_FORWARDED_FOR']
            else:
                ip = req.META['REMOTE_ADDR']
            params["_ip"] = ip

        req_inject_func.append(_func)
    if "_path" in params_key:
        def _func(req: HttpRequest, params: Dict):
            params["_path"] = req.path

        req_inject_func.append(_func)

    if "_req" in params_key:
        def _func(req: HttpRequest, params: Dict):
            params["_req"] = req

        req_inject_func.append(_func)

    if "_content" in params_key:
        def _func(req: HttpRequest, params: Dict):
            params["_content"] = req.body

        req_inject_func.append(_func)

    if "_orig" in params_key:
        def _func(req: Dict, params: Dict):
            params["_orig"] = req

        inject_func.append(_func)

    if "_params" in params_key:
        # noinspection PyUnusedLocal
        def _func(req: Dict, params: Dict):
            params["_params"] = dict(params)

        last_inject_func.append(_func)

    # noinspection PyTypeChecker
    def wrapper(req: Tuple[HttpRequest, Mapping]):
        is_req = isinstance(req, HttpRequest)
        if is_req:
            orig_params = {}
            orig_params.update(default_params)
            if len(req.POST):
                orig_params.update(to_simple_str_dict(req.POST))
            if len(req.GET):
                orig_params.update(to_simple_str_dict(req.GET))
            if len(req.FILES):
                orig_params.update(req.FILES)
            if len(req.COOKIES):
                for k, v in req.COOKIES.items():
                    orig_params["$c_%s" % k] = v
            req._orig_params = orig_params
        else:
            orig_params = dict(default_params)
            orig_params.update(req)
        if len(params_hints):
            params = {}
            if is_req:
                for each in req_inject_func:
                    each(req, params)
            for each in inject_func:
                each(orig_params, params)
            for k, hint in params_hints:  # type: Tuple[str,any]
                if k.startswith("_"):
                    continue
                if k not in orig_params:
                    raise Fail("缺少参数[%s]" % k)
                params[k] = get_data(orig_params[k], hint)
            for each in last_inject_func:
                each(orig_params, params)
            ret = func(**params)
        else:
            ret = func()
        if ret is None:
            ret = {"succ": True}
        return ret

    wrapper._is_action = True
    return wrapper


def HttpAction(func):
    _wrapper = Action(func)

    def wrapper(req):
        return to_response(_wrapper(req))

    return wrapper


class Handler:
    def __init__(self, req):
        self._req = req

    @abstractmethod
    def do(self):
        pass

    @classmethod
    def action(cls):
        def func(req):
            return to_response(cls(req).do())

        return func
