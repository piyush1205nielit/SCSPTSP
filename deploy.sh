#!/usr/bin/env bash
set -euo pipefail

# CONFIGURATION - Change repo URL to your actual repository
REPO_URL="https://github.com/piyush1205nielit/SCSPTSP.git"
APP_NAME="scsptsp"
TARGET_DIR="/home/ubuntu/${APP_NAME}"
PYTHON_BIN="python3"
VENV_DIR="${TARGET_DIR}/.venv"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
NGINX_SITE="/etc/nginx/sites-available/${APP_NAME}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${APP_NAME}"

DJANGO_PORT="${DJANGO_PORT:-8000}"
DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-127.0.0.1,localhost}"
DJANGO_DEBUG="${DJANGO_DEBUG:-False}"
DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-change-me-in-production}"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This script is written for Ubuntu/Debian EC2 instances (apt-get required)."
  exit 1
fi

# 1. Install System dependencies
sudo apt-get update -y
sudo apt-get install -y "$PYTHON_BIN" "${PYTHON_BIN}-venv" "${PYTHON_BIN}-pip" nginx git

# 2. Clone or Update the Repository
if [ ! -d "$TARGET_DIR" ]; then
  echo "Target directory doesn't exist. Cloning repository..."
  git clone "$REPO_URL" "$TARGET_DIR"
  cd "$TARGET_DIR"
else
  echo "Target directory exists. Pulling latest changes..."
  cd "$TARGET_DIR"
  # Reset any local changes to avoid conflicts and pull latest code
  git fetch --all
  git reset --hard origin/main
fi

# 3. Setup Python Virtual Environment inside the app directory
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip wheel

# Clean windows line endings if present in requirements.txt
TMP_REQUIREMENTS="$(mktemp)"
tr -d '\000' < requirements.txt | sed 's/\r$//' > "$TMP_REQUIREMENTS"
python -m pip install -r "$TMP_REQUIREMENTS"
python -m pip install gunicorn
rm -f "$TMP_REQUIREMENTS"

# 4. Write Production Environment File
cat > "${TARGET_DIR}/.env" <<EOF
DJANGO_ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS}
DJANGO_DEBUG=${DJANGO_DEBUG}
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
EOF

export DJANGO_ALLOWED_HOSTS DJANGO_DEBUG DJANGO_SECRET_KEY

# 5. Run Django migrations
python manage.py migrate --noinput

# 6. Manage Static Files
rm -rf "${TARGET_DIR}/staticfiles"
mkdir -p "${TARGET_DIR}/staticfiles"
if [ -f "${TARGET_DIR}/static/index.css" ]; then
  cp -f "${TARGET_DIR}/static/index.css" "${TARGET_DIR}/staticfiles/index.css"
fi

LOGO_FILE="$(find "${TARGET_DIR}/static" -maxdepth 1 -type f -iname 'logo.*' | head -n 1 || true)"
if [ -n "$LOGO_FILE" ]; then
  cp -f "$LOGO_FILE" "${TARGET_DIR}/staticfiles/"
fi

find "${TARGET_DIR}/staticfiles" -type f ! -iname 'index.css' ! -iname 'logo.*' -delete

# 7. Create Systemd Service File (Runs under the actual user context, not root)
CURRENT_USER="${SUDO_USER:-$(whoami)}"
cat | sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=${APP_NAME} Django service
After=network.target

[Service]
User=${CURRENT_USER}
Group=www-data
WorkingDirectory=${TARGET_DIR}
EnvironmentFile=${TARGET_DIR}/.env
ExecStart=${VENV_DIR}/bin/gunicorn --workers 3 --bind 127.0.0.1:${DJANGO_PORT} student.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 8. Setup Nginx configuration
cat | sudo tee "$NGINX_SITE" >/dev/null <<EOF
server {
    listen 80;
    server_name _;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias ${TARGET_DIR}/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:${DJANGO_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Link Nginx site configuration
sudo ln -sf "$NGINX_SITE" "$NGINX_ENABLED"
sudo rm -f /etc/nginx/sites-enabled/default

# 9. Restart processes to apply updates
sudo systemctl daemon-reload
sudo systemctl enable "${APP_NAME}.service"
sudo systemctl restart "${APP_NAME}.service"
sudo nginx -t
sudo systemctl restart nginx

echo "Deployment prep complete. App is cloned and configured successfully."