#!/usr/bin/env bash
export RABBITMQ_HOST=iosstore.sklxsj.com
export RABBITMQ_PASS=q1w2e3r4
export SQLITE_FORCE=TRUE
python3.6 -m celery worker -A ios_ci --loglevel INFO