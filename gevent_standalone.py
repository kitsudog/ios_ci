from __future__ import print_function

from gevent import monkey

monkey.patch_all()
from gevent import wsgi

from ios_ci.wsgi import application

print('Serving on 8000...')
wsgi.WSGIServer(("0.0.0.0", 8000), application).serve_forever()
