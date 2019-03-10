#!/usr/bin/env bash
# 为click框架初始化一下
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
if [ "${PASS_REQUIREMENTS:-FALSE}" == "FALSE" ]
then
    # 这个优化是给内网环境准备的
    pip3 install --trusted-host mirrors.aliyun.com -i http://mirrors.aliyun.com/pypi/simple -r requirements.txt
fi

# suit 打补丁
function patch_suit(){
    base=`python3.6 -c 'import suit,os;print(os.path.dirname(suit.__file__))'`
    sed -i 's/from django.core.urlresolvers /from django.urls /g' $base/templatetags/suit_tags.py
    sed -i 's/@register.assignment_tag/@register.simple_tag/g' $base/templatetags/suit_tags.py
    sed -i 's/from django.core.urlresolvers /from django.urls /g' $base/templatetags/suit_menu.py
    sed -i 's/@register.assignment_tag/@register.simple_tag/g' $base/templatetags/suit_menu.py
}
patch_suit

python3.6 manage.py collectstatic --no-input
python3.6 manage.py makemigrations --noinput
python3.6 manage.py migrate

# todo: celery -B 只用于debug模式
nohup celery worker -A loop -B --loglevel INFO --logfile /var/log/server/celery.log &

if [ ${UWSGI:-FALSE} = "TRUE" -o ${VIRTUAL_PROTO:-http} = "uwsgi" ]
then
    uwsgi --socket :8000 --gevent --gevent-monkey-patch --module open.wsgi  --async 100 --http-keepalive --chmod-socket=664
else
    python3.6 manage.py runserver 0.0.0.0:8000
fi
