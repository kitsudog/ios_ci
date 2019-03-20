#!/usr/bin/env bash
export RABBITMQ_HOST=iosstore_flower.sklxsj.com
export RABBITMQ_PASS=q1w2e3r4
python3.6 -m celery worker -A ios_ci --loglevel INFO