#!/bin/bash

# AWS EC2 Quick Deployment Script
# This script automates the basic setup of the registry on a fresh Ubuntu EC2 instance
# Usage: bash deploy.sh

set -e

echo "=== ACME Trustworthy Model Registry - AWS EC2 Deployment ==="
echo ""

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use: sudo bash deploy.sh)"
   exit 1
fi

# Configuration
REPO_URL="${1:-https://github.com/bchiang100/trustworthy-model-registry.git}"
APP_DIR="/var/www/trustworthy-model-registry"
APP_USER="ubuntu"
DOMAIN="${2:-localhost}"

echo "Configuration:"
echo "  Repository: $REPO_URL"
echo "  Install Directory: $APP_DIR"
echo "  Domain: $DOMAIN"
echo "  App User: $APP_USER"
echo ""

# Step 1: System updates
echo "[1/8] Updating system packages..."
apt update && apt upgrade -y

# Step 2: Install dependencies
echo "[2/8] Installing system dependencies..."
apt install -y python3.12 python3.12-venv python3-pip git curl nginx certbot python3-certbot-nginx

# Step 3: Create app directory
echo "[3/8] Creating application directory..."
mkdir -p "$APP_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR"

# Step 4: Clone repository
echo "[4/8] Cloning repository..."
cd "$APP_DIR"
sudo -u "$APP_USER" git clone "$REPO_URL" . || git pull

# Step 5: Setup Python environment
echo "[5/8] Setting up Python virtual environment..."
cd "$APP_DIR"
sudo -u "$APP_USER" python3.12 -m venv venv || sudo -u "$APP_USER" python3 -m venv venv
sudo -u "$APP_USER" bash -c 'source venv/bin/activate && pip install --upgrade pip setuptools wheel'
sudo -u "$APP_USER" bash -c 'source venv/bin/activate && pip install -e .'
sudo -u "$APP_USER" bash -c 'source venv/bin/activate && pip install gunicorn uvicorn'

# Step 6: Create environment file
echo "[6/8] Creating environment configuration..."
cat > "$APP_DIR/.env" << EOF
ENVIRONMENT=production
API_HOST=0.0.0.0
API_PORT=8000
ALLOWED_ORIGINS=http://$DOMAIN,https://$DOMAIN,http://www.$DOMAIN,https://www.$DOMAIN
LOG_LEVEL=info
EOF
chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"
echo "  Created: $APP_DIR/.env"

# Step 7: Setup Nginx
echo "[7/8] Configuring Nginx reverse proxy..."
cat > /etc/nginx/sites-available/registry << EOF
upstream registry_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 100M;

    location / {
        proxy_pass http://registry_api;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/registry /etc/nginx/sites-enabled/registry
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
echo "  Nginx configured and started"

# Step 8: Create systemd service
echo "[8/8] Creating systemd service..."
cat > /etc/systemd/system/registry.service << EOF
[Unit]
Description=ACME Trustworthy Model Registry
After=network.target

[Service]
Type=notify
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn \\
    -w 4 \\
    -k uvicorn.workers.UvicornWorker \\
    --bind 0.0.0.0:8000 \\
    --access-logfile - \\
    --error-logfile - \\
    src.acme_cli.api.main:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable registry
systemctl start registry

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next Steps:"
echo "1. Wait a few seconds for the service to start"
echo "2. Check service status: sudo systemctl status registry"
echo "3. View logs: sudo journalctl -u registry -f"
echo "4. Open browser: http://$DOMAIN"
echo ""
echo "To setup SSL (recommended):"
echo "  sudo certbot --nginx -d $DOMAIN"
echo ""
echo "For more information, see AWS_EC2_DEPLOYMENT.md"
