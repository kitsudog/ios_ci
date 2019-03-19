# Create your views here.
import os

from django.http import HttpResponse

from base.utils import read_binary_file


def static_dir(request):
    with open("static/" + request.path) as fin:
        content = fin.read()
    return HttpResponse(content)


mime = {
    "js": "application/javascript",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "ico": "image/x-ico",
    "gif": "image/gif",
    "css": "text/css",
}


def static(request):
    """
    """
    file = "static/" + request.path[1:]
    if os.path.isfile(file):
        content = read_binary_file(file)
        ext = request.path.rpartition(".")[-1].lower()
        if ext in {"jpg", "jpeg"}:
            return HttpResponse(content, content_type=mime.get(ext, "image/jpeg"))
        elif ext in {"js"}:
            return HttpResponse(content, content_type=mime.get(ext, "application/javascript"))
        elif ext in {"gif"}:
            return HttpResponse(content, content_type=mime.get(ext, "image/gif"))
        elif ext in {"xml"}:
            return HttpResponse(content, content_type=mime.get(ext, "text/xml"))
        elif ext in {"css"}:
            return HttpResponse(content, content_type=mime.get(ext, "text/css"))
        elif ext in {"html", "htm", "shtml"}:
            return HttpResponse(content, content_type=mime.get(ext, "text/html"))
        elif ext in {"png"}:
            return HttpResponse(content, content_type=mime.get(ext, "image/png"))
        elif ext in {"svg", "svgz"}:
            return HttpResponse(content, content_type=mime.get(ext, "image/svg+xml"))
        elif ext in {"ico"}:
            return HttpResponse(content, content_type=mime.get(ext, "image/x-icon"))
        else:
            return HttpResponse(content, content_type=mime.get(ext, "text/plain"))
    return HttpResponse("", status=404)


def static_php(request):
    """
    用来实现.php文件转发的
    """
    with open("static/" + request.path[1:].replace(".php", ".html")) as fin:
        content = fin.read()
    return HttpResponse(content)
