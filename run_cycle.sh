#!/bin/bash
cd /mnt/storage/websites/leaploop
export LEAPLOOP_SECRETS=/opt/homeserver/leaploop/secrets.env
mkdir -p data
.venv/bin/python -m engine.run >> data/watcher.log 2>&1
