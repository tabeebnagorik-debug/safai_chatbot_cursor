#!/bin/bash
# Quick deployment script for Safai API on Ubuntu Server
# Run with: bash deployment/quick-start.sh

set -e

echo "🚀 Starting Safai API Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

# Variables
APP_DIR="/opt/safai-api"
SERVICE_FILE="deployment/safai-api.service"
NGINX_FILE="deployment/nginx-safai-api.conf"

# Step 1: Install UV
echo -e "${YELLOW}Step 1: Installing UV...${NC}"
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
else
    echo -e "${GREEN}UV is already installed${NC}"
fi

# Step 2: Install system packages
echo -e "${YELLOW}Step 2: Installing system packages...${NC}"
apt update
apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx git curl build-essential

# Step 3: Create application directory
echo -e "${YELLOW}Step 3: Setting up application directory...${NC}"
mkdir -p $APP_DIR
chown $SUDO_USER:$SUDO_USER $APP_DIR

# Step 4: Copy files (assuming script is run from project root)
echo -e "${YELLOW}Step 4: Copying application files...${NC}"
if [ -f "main.py" ]; then
    cp -r . $APP_DIR/
    chown -R $SUDO_USER:$SUDO_USER $APP_DIR
else
    echo -e "${RED}Error: main.py not found. Please run this script from the project root.${NC}"
    exit 1
fi

# Step 5: Install dependencies with UV
echo -e "${YELLOW}Step 5: Installing Python dependencies...${NC}"
cd $APP_DIR
if [ -f "pyproject.toml" ]; then
    uv sync
else
    uv venv
    source .venv/bin/activate
    uv pip install -r requirements.txt
fi

# Step 6: Setup .env file
echo -e "${YELLOW}Step 6: Setting up environment variables...${NC}"
if [ ! -f "$APP_DIR/.env" ]; then
    echo "Creating .env file..."
    cat > $APP_DIR/.env << EOF
OPENAI_API_KEY=your_openai_api_key_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=safai_chat_db
DB_USER=postgres
DB_PASSWORD=
EOF
    echo -e "${YELLOW}Please edit $APP_DIR/.env and add your API keys and database credentials${NC}"
fi

# Step 7: Initialize database
echo -e "${YELLOW}Step 7: Initializing database...${NC}"
cd $APP_DIR
uv run python init_tables.py

# Step 8: Setup systemd service
echo -e "${YELLOW}Step 8: Setting up systemd service...${NC}"
UV_PATH=$(which uv)
if [ -z "$UV_PATH" ]; then
    UV_PATH="/usr/local/bin/uv"
fi

# Update service file with correct UV path
sed "s|ExecStart=.*|ExecStart=$UV_PATH run fastapi run main.py --host 127.0.0.1 --port 8000|" $SERVICE_FILE > /tmp/safai-api.service
cp /tmp/safai-api.service /etc/systemd/system/safai-api.service

# Set permissions
chown -R www-data:www-data $APP_DIR
chmod 600 $APP_DIR/.env

# Enable and start service
systemctl daemon-reload
systemctl enable safai-api
systemctl start safai-api

# Step 9: Setup Nginx
echo -e "${YELLOW}Step 9: Setting up Nginx...${NC}"
cp $NGINX_FILE /etc/nginx/sites-available/safai-api
ln -sf /etc/nginx/sites-available/safai-api /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# Step 10: Setup firewall
echo -e "${YELLOW}Step 10: Configuring firewall...${NC}"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo -e "${GREEN}✅ Deployment completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Edit $APP_DIR/.env with your API keys and database credentials"
echo "2. Update /etc/nginx/sites-available/safai-api with your domain name"
echo "3. Check service status: sudo systemctl status safai-api"
echo "4. Check logs: sudo journalctl -u safai-api -f"
echo "5. Test API: curl http://localhost:8000/health"

