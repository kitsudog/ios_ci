#!/usr/bin/env bash
# 为click框架初始化一下
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
if [[ "${PASS_REQUIREMENTS:-FALSE}" == "FALSE" ]]
then
    # 这个优化是给内网环境准备的
    pip3.6 install --trusted-host mirrors.aliyun.com -i http://mirrors.aliyun.com/pypi/simple -r requirements.txt
fi

if [[ ! -x /usr/local/bin/uwsgi ]]
then
    pip3.6 install --trusted-host mirrors.aliyun.com -i http://mirrors.aliyun.com/pypi/simple -I uwsgi
fi

python3.6 manage.py collectstatic --no-input
python3.6 manage.py makemigrations --noinput
python3.6 manage.py migrate

if [[ ${FLOWER_ONLY:-FALSE} = "TRUE" ]]
then
    python3.6 -m celery flower -A ios_ci
    exit
fi


#nohup python3.6 -m celery worker -A ios_ci --loglevel INFO --logfile /var/log/server/celery.log &


mkdir -p /data/income
mkdir -p /data/projects

ln -s /data/income /app/server/static/income
ln -s /data/projects /app/server/static/projects

ln -s /data/income /var/www/html
ln -s /data/projects /var/www/html


if [[ ${UWSGI:-FALSE} = "TRUE" || ${VIRTUAL_PROTO:-http} = "uwsgi" ]]
then
    uwsgi --socket :8000 --gevent --gevent-monkey-patch --module ios_ci.wsgi  --async 100 --http-keepalive --chmod-socket=664
else
    nohup python3.6 -m celery flower -A ios_ci &
    python3.6 manage.py runserver 0.0.0.0:8000
fi
