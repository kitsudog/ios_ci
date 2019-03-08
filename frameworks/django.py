from collections import Mapping

from django.http import HttpResponse, HttpRequest
from django.utils.deprecation import MiddlewareMixin

from base.style import Trace, json_str
from frameworks.base import to_response


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class JsonResponseHandler(MiddlewareMixin):

    def process_response(self, request, response):
        if isinstance(response, Mapping):
            return to_response(response)
        return response

    def process_exception(self, request: HttpRequest, e: Exception):
        Trace("执行[%s][%s]出错" % (request.path, json_str(getattr(request, "_orig_params", {}))[:1000]), e)
        msg = str(e) if isinstance(e, AssertionError) else "服务器出错"
        if len(msg) > 1000:
            msg = msg[:996] + " ..."
        return HttpResponse(json_str({
            "ret": -1,
            "error": msg,
        }), content_type="application/json", status=500)
