# Ubuntu Server Deployment Guide with UV

This guide will help you deploy the Safai AI Chat Agent API on an Ubuntu server using `uv run fastapi run`.

## Prerequisites

- Ubuntu 20.04 LTS or later
- Root or sudo access
- Domain name (optional, for SSL)
- PostgreSQL installed and running

## Step 1: Server Setup

### 1.1 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Required Packages

```bash
sudo apt install -y python3 python3-pip python3-venv
sudo apt install -y postgresql postgresql-contrib
sudo apt install -y nginx
sudo apt install -y git curl
sudo apt install -y build-essential
```

### 1.3 Install UV

UV is a fast Python package installer and resolver. Install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or using pip:

```bash
pip install uv
```

After installation, add UV to PATH (if not already added):

```bash
export PATH="$HOME/.cargo/bin:$PATH"
# Or add to ~/.bashrc or ~/.zshrc for persistence
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verify installation:

```bash
uv --version
```

## Step 2: Application Setup

### 2.1 Create Application Directory

```bash
sudo mkdir -p /opt/safai-api
sudo chown $USER:$USER /opt/safai-api
```

### 2.2 Clone or Upload Your Code

**Option A: Using Git**
```bash
cd /opt/safai-api
git clone <your-repo-url> .
```

**Option B: Using SCP/SFTP**
```bash
# From your local machine
scp -r /path/to/ai-chat-agent-backend/* user@your-server:/opt/safai-api/
```

### 2.3 Install UV in Project

UV will automatically create and manage the virtual environment:

```bash
cd /opt/safai-api
uv sync  # This will install all dependencies from requirements.txt
```

Or if you don't have a `pyproject.toml`, install directly:

```bash
cd /opt/safai-api
uv venv  # Create virtual environment
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2.4 Set Up Environment Variables

```bash
cd /opt/safai-api
nano .env
```

Add the following variables:

```env
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=safai_chat_db
DB_USER=postgres
DB_PASSWORD=your_db_password_here
```

### 2.5 Set Up PostgreSQL Database

```bash
sudo -u postgres psql
```

In PostgreSQL prompt:

```sql
CREATE DATABASE safai_chat_db;
CREATE USER safai_user WITH PASSWORD 'your_secure_password';
ALTER ROLE safai_user SET client_encoding TO 'utf8';
ALTER ROLE safai_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE safai_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE safai_chat_db TO safai_user;
\q
```

Update your `.env` file with the database credentials.

### 2.6 Initialize Database Tables

```bash
cd /opt/safai-api
uv run python init_tables.py
```

## Step 3: Configure Systemd Service

### 3.1 Update Service File Path

Edit the service file to ensure UV path is correct:

```bash
# Check where UV is installed
which uv
# Output might be: /usr/local/bin/uv or /home/username/.cargo/bin/uv
```

### 3.2 Copy and Configure Systemd Service File

```bash
sudo cp deployment/safai-api.service /etc/systemd/system/
sudo nano /etc/systemd/system/safai-api.service
```

Update the service file with correct paths:

```ini
[Unit]
Description=Safai AI Chat Agent API
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/safai-api
Environment="PATH=/usr/local/bin:/usr/bin:/bin:/home/username/.cargo/bin"
Environment="UV_PROJECT_ENVIRONMENT=/opt/safai-api/.venv"
ExecStart=/usr/local/bin/uv run fastapi run main.py --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Important adjustments:**
- Update `ExecStart` path to where UV is installed (check with `which uv`)
- Update `User` and `Group` if using a different user
- Ensure `WorkingDirectory` points to `/opt/safai-api`

### 3.3 Set Proper Permissions

```bash
sudo chown -R www-data:www-data /opt/safai-api
sudo chmod 600 /opt/safai-api/.env  # Protect .env file
```

### 3.4 Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable safai-api
sudo systemctl start safai-api
sudo systemctl status safai-api
```

### 3.5 View Logs

```bash
# View service logs
sudo journalctl -u safai-api -f

# View recent logs
sudo journalctl -u safai-api -n 100
```

## Step 4: Configure Nginx

### 4.1 Copy Nginx Configuration

```bash
sudo cp deployment/nginx-safai-api.conf /etc/nginx/sites-available/safai-api
```

### 4.2 Update Configuration

```bash
sudo nano /etc/nginx/sites-available/safai-api
```

Update:
- `server_name`: Replace with your domain name

### 4.3 Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/safai-api /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

### 4.4 Remove Default Site (Optional)

```bash
sudo rm /etc/nginx/sites-enabled/default
sudo systemctl reload nginx
```

## Step 5: SSL Certificate (Optional but Recommended)

### 5.1 Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 5.2 Obtain SSL Certificate

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### 5.3 Update Nginx Configuration

After obtaining the certificate, uncomment the HTTPS section in `/etc/nginx/sites-available/safai-api` and update certificate paths.

### 5.4 Auto-renewal

Certbot sets up auto-renewal automatically. Test it:

```bash
sudo certbot renew --dry-run
```

## Step 6: Firewall Configuration

### 6.1 Configure UFW

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

## Step 7: Testing

### 7.1 Test API Health

```bash
curl http://localhost:8000/health
# or
curl http://your-domain.com/health
```

### 7.2 Test Initiate Chat

```bash
curl -X POST http://your-domain.com/auth/initiate-chat \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+8801712345678"}'
```

## Step 8: Application Updates

### 8.1 Update Code

```bash
cd /opt/safai-api
git pull  # If using git
# Or upload new files via SCP/SFTP
```

### 8.2 Update Dependencies

```bash
cd /opt/safai-api
uv sync  # If using pyproject.toml
# Or
uv pip install -r requirements.txt --upgrade
```

### 8.3 Restart Service

```bash
sudo systemctl restart safai-api
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status safai-api

# Check logs
sudo journalctl -u safai-api -n 100

# Verify UV path
which uv
/usr/local/bin/uv --version

# Test running manually
cd /opt/safai-api
uv run fastapi run main.py --host 127.0.0.1 --port 8000
```

### UV Not Found Error

If systemd can't find UV:

1. Find UV path:
   ```bash
   which uv
   ```

2. Update service file `ExecStart` with full path

3. Or create symlink:
   ```bash
   sudo ln -s $(which uv) /usr/local/bin/uv
   ```

### Permission Issues

```bash
# Check ownership
ls -la /opt/safai-api

# Fix ownership if needed
sudo chown -R www-data:www-data /opt/safai-api
sudo chmod 600 /opt/safai-api/.env
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
sudo -u postgres psql -d safai_chat_db

# Check PostgreSQL status
sudo systemctl status postgresql

# Verify .env file
sudo cat /opt/safai-api/.env | grep DB_
```

### Nginx Issues

```bash
# Test configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/safai-api-error.log
```

## Alternative: Using UV with systemd (Different Approach)

If you prefer to use UV's virtual environment directly:

```ini
[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/safai-api
Environment="PATH=/opt/safai-api/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/safai-api/.venv/bin/fastapi run main.py --host 127.0.0.1 --port 8000
```

This requires installing fastapi-cli in the virtual environment:

```bash
cd /opt/safai-api
uv pip install "fastapi[standard]"
```

## Performance Tuning

### Increase Workers (if using Gunicorn instead)

If you want to use multiple workers, you'll need to use Gunicorn or Uvicorn workers:

```bash
uv pip install gunicorn uvicorn[standard]
```

Then update service file:

```ini
ExecStart=/usr/local/bin/uv run gunicorn main:api_app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000
```

## Security Recommendations

1. **Update CORS settings** in `main.py`:
   ```python
   api_app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-frontend-domain.com"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

2. **Protect .env file**:
   ```bash
   sudo chmod 600 /opt/safai-api/.env
   sudo chown www-data:www-data /opt/safai-api/.env
   ```

3. **Regular backups**:
   ```bash
   # Database backup
   pg_dump safai_chat_db > backup_$(date +%Y%m%d).sql
   ```

## Support

For issues, check:
- Service logs: `sudo journalctl -u safai-api -f`
- Nginx logs: `sudo tail -f /var/log/nginx/safai-api-error.log`
- Application logs: Check journalctl output

