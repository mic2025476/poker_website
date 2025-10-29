#!/usr/bin/env bash
set -e
cd /home/ubuntu/poker_website
git pull
source env/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
deactivate
sudo systemctl restart gunicorn-poker
sudo systemctl reload nginx || true
echo "Deploy complete."
