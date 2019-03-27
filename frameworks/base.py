import inspect
import json
from datetime import datetime
from typing import Tuple, List, Mapping, Type, Dict, Callable

from django.http import HttpResponse, HttpRequest

from base.style import Fail, json_str, ExJSONEncoder, Trace
from base.utils import str_to_bool, DecorateHelper


def get_data(value: str, hint_type: Type, default_value: any = None) -> any:
    if hint_type in {bool, True, False}:
        return str_to_bool(value)
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


class DjangoExJSONEncoder(ExJSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return int(o.timestamp() * 1000)
        super().default(o)


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
    }, cls=DjangoExJSONEncoder), content_type="application/json")
    rsp["Access-Control-Allow-Origin"] = "*"
    rsp["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return rsp


# noinspection PyAttributeOutsideInit
class DjangoAction(DecorateHelper):

    def prepare(self):
        self.func_title = "%s.%s" % (self.func.__module__.split(".")[-1], self.func.__name__)
        self._is_action = True
        self._orig_func = self.func
        self.default_params = {}
        self.params_hints = {}

    def wrapper(self, request, *args, **kwargs):
        return HttpResponse(json_str(self.func(request)))


# noinspection PyPep8Naming,PyAttributeOutsideInit
class Action(DjangoAction):

    def pre_wrapper(self, request: HttpRequest, orig_params, *args, **kwargs):
        pass

    def prepare(self):
        super().prepare()
        # todo: 反射处理
        spec = inspect.getfullargspec(self.func)
        self.default_params, self.params_hints = inject_params(spec.args, spec.defaults, spec.annotations)
        params_key = list(zip(*self.params_hints))
        params_key = params_key[0] if len(params_key) else []
        self.req_inject_func = []  # type:List[Callable[[HttpRequest],Dict]]
        self.inject_func = []  # type:List[Callable[[Dict],None]]
        self.last_inject_func = []  # type:List[Callable[[Dict],None]]
        if "_ip" in params_key:
            def _func(req: HttpRequest, params: Dict):
                if "HTTP_X_FORWARDED_FOR" in req.META:
                    ip = req.META['HTTP_X_FORWARDED_FOR']
                else:
                    ip = req.META['REMOTE_ADDR']
                params["_ip"] = ip

            self.req_inject_func.append(_func)
        if "_path" in params_key:
            def _func(req: HttpRequest, params: Dict):
                params["_path"] = req.path

            self.req_inject_func.append(_func)

        if "_req" in params_key:
            def _func(req: HttpRequest, params: Dict):
                params["_req"] = req

            self.req_inject_func.append(_func)

        if "_content" in params_key:
            def _func(req: HttpRequest, params: Dict):
                params["_content"] = req.body

            self.req_inject_func.append(_func)

        if "_orig" in params_key:
            def _func(req: Dict, params: Dict):
                params["_orig"] = req

            self.inject_func.append(_func)

        if "_params" in params_key:
            # noinspection PyUnusedLocal
            def _func(req: Dict, params: Dict):
                params["_params"] = dict(params)

            self.last_inject_func.append(_func)

    def wrapper(self, req: HttpRequest, *args, **kwargs):
        is_req = isinstance(req, HttpRequest)
        if is_req:
            orig_params = {}
            orig_params.update(self.default_params)
            if len(req.POST):
                orig_params.update(to_simple_str_dict(req.POST))
            if len(req.GET):
                orig_params.update(to_simple_str_dict(req.GET))
            if len(req.FILES):
                for f, c in req.FILES.items():
                    orig_params[f] = c.read()
            if len(req.COOKIES):
                for k, v in req.COOKIES.items():
                    orig_params["$c_%s" % k] = v
            content_type = req.META.get("CONTENT_TYPE", "")
            if content_type.startswith('multipart'):
                pass
            elif len(req.body):
                if "json" in content_type:
                    orig_params.update(json.loads(req.body.decode('utf8')))
                elif "text" in content_type:
                    orig_params.update(json.loads(req.body.decode('utf8')))

            req._orig_params = orig_params
        else:
            orig_params = dict(self.default_params)
            orig_params.update(req)

        # noinspection PyNoneFunctionAssignment
        pre_ret = self.pre_wrapper(req, orig_params, *args, **kwargs)
        if pre_ret is not None:
            if pre_ret is True:
                pass
            else:
                return pre_ret
        params = {}
        if len(self.params_hints):
            if is_req:
                for each in self.req_inject_func:
                    each(req, params)
            for each in self.inject_func:
                each(orig_params, params)
            for k, hint in self.params_hints:  # type:Tuple[str,any]
                if k.startswith("_"):
                    continue
                if k not in orig_params:
                    raise Fail("缺少参数[%s]" % k)
                params[k] = get_data(orig_params[k], hint)
            for each in self.last_inject_func:
                each(orig_params, params)
        try:
            ret = self.func(**params)
            if ret is None:
                ret = {
                    "succ": True,
                }
        except Exception as e:
            # _be_log = req._log if is_req else req.get("_log")  # type:BeLog
            # if _be_log:
            #     _be_log.ret = str(e)
            Trace("出现异常", e)
            raise e
        finally:
            # with Block("处理log部分", fail=False):
            #     _be_log = req._log if is_req else req.get("_log")  # type:BeLog
            #     if _be_log:
            #         _be_log.save()
            pass
        return ret
