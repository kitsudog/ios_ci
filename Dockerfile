FROM daocloud.io/dayun_server/pyrun:master
RUN pip3.6 install gevent requests xmltodict uwsgi pycrypto==2.6.1 rsa==3.4.2 pymongo redis hyper mysqlclient biplist uncurl pyjwt==1.7.1 pyopenssl
RUN pip3.6 install celery[redis,gevent]
RUN pip3.6 install django django-suit

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8
