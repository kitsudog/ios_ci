# Create your views here.
import os

from django.http import HttpResponse


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
    用来实现.php文件转发的
    """
    file = "static/" + request.path[1:]
    if os.path.isfile(file):
        with open(file, mode="br") as fin:
            content = fin.read()
        ext = request.path.rpartition(".")[-1]
        return HttpResponse(content, content_type=mime.get(ext, "text/plain"))
    return HttpResponse("", status=404)


def static_php(request):
    """
    用来实现.php文件转发的
    """
    with open("static/" + request.path[1:].replace(".php", ".html")) as fin:
        content = fin.read()
    return HttpResponse(content)
