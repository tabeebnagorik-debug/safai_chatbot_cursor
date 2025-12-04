# Nginx Setup for Combined Laravel + FastAPI

This guide shows how to add the FastAPI Chat Agent API to your existing Laravel Nginx configuration.

## Option 1: API at `/ai/` (Recommended - Removes /ai prefix)

This configuration removes the `/ai` prefix when forwarding to FastAPI, so your FastAPI endpoints work as-is.

**Example:**
- Request: `https://developer-st.safai.com.bd/ai/health`
- Forwarded to: `http://127.0.0.1:8990/health`

**Use this file:** `nginx-safai-combined.conf`

## Option 2: API at `/ai/` (Keeps /ai prefix)

This configuration keeps the `/ai` prefix when forwarding.

**Example:**
- Request: `https://developer-st.safai.com.bd/ai/health`
- Forwarded to: `http://127.0.0.1:8990/ai/health`

**Use this file:** `nginx-safai-combined-alt.conf`

## Setup Instructions

### Step 1: Backup Current Configuration

```bash
sudo cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup
# Or if you have a specific config file:
sudo cp /etc/nginx/sites-available/your-laravel-config /etc/nginx/sites-available/your-laravel-config.backup
```

### Step 2: Copy New Configuration

Choose one of the options above and copy the configuration:

```bash
# Option 1: Remove /ai prefix (Recommended)
sudo cp /var/www/ai-chat-agent/deployment/nginx-safai-combined.conf /etc/nginx/sites-available/developer-st.safai.com.bd

# OR Option 2: Keep /ai prefix
sudo cp /var/www/ai-chat-agent/deployment/nginx-safai-combined-alt.conf /etc/nginx/sites-available/developer-st.safai.com.bd
```

### Step 3: Test Configuration

```bash
sudo nginx -t
```

### Step 4: Reload Nginx

```bash
sudo systemctl reload nginx
```

## Testing

### Test Laravel (should still work):
```bash
curl https://developer-st.safai.com.bd/
```

### Test FastAPI Health Endpoint:
```bash
# If using Option 1 (removes /ai prefix):
curl https://developer-st.safai.com.bd/ai/health

# If using Option 2 (keeps /ai prefix):
curl https://developer-st.safai.com.bd/ai/health
```

### Test FastAPI Initiate Chat:
```bash
curl -X POST https://developer-st.safai.com.bd/ai/auth/initiate-chat \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+8801712345678"}'
```

## API Endpoints Mapping

With the recommended configuration (Option 1), your FastAPI endpoints will be accessible at:

- `https://developer-st.safai.com.bd/ai/health` → Health check
- `https://developer-st.safai.com.bd/ai/auth/initiate-chat` → Initiate chat
- `https://developer-st.safai.com.bd/ai/chat` → Send chat message
- `https://developer-st.safai.com.bd/ai/sessions/{session_id}/history` → Get chat history
- `https://developer-st.safai.com.bd/ai/docs` → API documentation

## Troubleshooting

### If Laravel routes break:

Make sure the FastAPI location block comes **before** the Laravel location block in the config.

### If FastAPI returns 404:

1. Check if FastAPI is running:
   ```bash
   curl http://127.0.0.1:8990/health
   ```

2. Check Nginx error logs:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

3. Verify the proxy_pass URL is correct:
   - Should be: `http://127.0.0.1:8990` (with trailing slash if using Option 2)

### If CORS errors:

The configuration includes CORS headers. If you need to restrict origins, update:

```nginx
add_header Access-Control-Allow-Origin https://your-frontend-domain.com always;
```

## Alternative: Use Different Subdomain

If you prefer, you can also set up a subdomain like `api.developer-st.safai.com.bd`:

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/letsencrypt/live/developer-st.safai.com.bd/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/developer-st.safai.com.bd/privkey.pem;
    
    server_name api.developer-st.safai.com.bd;
    
    location / {
        proxy_pass http://127.0.0.1:8990;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
```

Then access API at: `https://api.developer-st.safai.com.bd/health`

