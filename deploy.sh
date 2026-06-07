#!/usr/bin/env bash
set -eo pipefail

APP_NAME="SCSPTSP"
TARGET_DIR="/home/ubuntu/${APP_NAME}"

cd "$TARGET_DIR"
git fetch --all
git reset --hard origin/main

source "${TARGET_DIR}/.venv/bin/activate"

python -m pip install --upgrade pip wheel -q
python -m pip install -r requirements.txt -q
python -m pip install gunicorn -q

python manage.py migrate --noinput

python manage.py collectstatic --noinput --clear

sudo systemctl daemon-reload
sudo systemctl restart "${APP_NAME}.service"
sudo nginx -t && sudo systemctl restart nginx

echo "Deployment complete."
