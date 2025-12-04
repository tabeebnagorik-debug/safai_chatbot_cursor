# Safai AI Chat Agent API

FastAPI REST API for Safai's AI Customer Support Assistant powered by LangGraph and RAG.

## Installation

### Prerequisites

Install `uv` (if not already installed):
```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

### Setup

1. Install dependencies and create virtual environment:
```bash
uv sync
```

This will:
- Create a virtual environment (`.venv`) if it doesn't exist
- Install all dependencies from `pyproject.toml`
- Create/update the lock file for reproducible builds

2. Activate the virtual environment:
```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

## Running the API Server

```bash
# Activate virtual environment (if not already activated)
source .venv/bin/activate

# Run the API server
python main.py
```

Or using uv to run directly:
```bash
uv run python main.py
```

Or using uvicorn directly:
```bash
# With activated venv
uvicorn main:api_app --host 0.0.0.0 --port 8000 --reload

# Or with uv
uv run uvicorn main:api_app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- API: http://localhost:8000
- Interactive API Docs: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

## API Endpoints

### 1. Root Endpoint
**GET** `/`

Returns API information.

**Response:**
```json
{
  "name": "Safai AI Chat Agent API",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs",
  "health": "/health"
}
```

### 2. Health Check
**GET** `/health`

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00.000000"
}
```

### 3. Chat Endpoint
**POST** `/chat`

Send a message to the AI chat agent and receive a response.

**Request Body:**
```json
{
  "message": "What are your cleaning service prices?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Our cleaning services start at...",
  "session_id": "api_session_abc123",
  "timestamp": "2025-01-15T10:30:00.000000"
}
```

**Notes:**
- If `session_id` is not provided, a new session will be created automatically
- Use the same `session_id` in subsequent requests to maintain conversation context
- The conversation history is maintained using LangGraph checkpoints

### 4. Get Session History
**GET** `/sessions/{session_id}/history`

Retrieve conversation history for a specific session.

**Response:**
```json
{
  "success": true,
  "session_id": "api_session_abc123",
  "message_count": 4,
  "messages": [
    {
      "role": "user",
      "content": "What are your prices?"
    },
    {
      "role": "assistant",
      "content": "Our cleaning services start at..."
    }
  ]
}
```

### 5. Clear Session
**DELETE** `/sessions/{session_id}`

Clear/reset a conversation session.

**Response:**
```json
{
  "success": true,
  "message": "Session api_session_abc123 can be reset. Send a new message to start fresh.",
  "session_id": "api_session_abc123"
}
```

## Usage Examples

### Python Example

```python
import requests

# Base URL
BASE_URL = "http://localhost:8000"

# Send a chat message
response = requests.post(
    f"{BASE_URL}/chat",
    json={
        "message": "What are your cleaning service prices?"
    }
)

data = response.json()
print(f"AI Response: {data['message']}")
print(f"Session ID: {data['session_id']}")

# Continue conversation with same session
response = requests.post(
    f"{BASE_URL}/chat",
    json={
        "message": "What about weekly cleaning?",
        "session_id": data['session_id']
    }
)

print(f"AI Response: {response.json()['message']}")

# Get conversation history
history = requests.get(
    f"{BASE_URL}/sessions/{data['session_id']}/history"
)
print(history.json())
```

### JavaScript/TypeScript Example

```javascript
const BASE_URL = 'http://localhost:8000';

// Send a chat message
async function sendMessage(message, sessionId = null) {
  const response = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: message,
      session_id: sessionId
    })
  });
  
  return await response.json();
}

// Usage
const firstResponse = await sendMessage('What are your prices?');
console.log(firstResponse.message);
console.log('Session ID:', firstResponse.session_id);

// Continue conversation
const secondResponse = await sendMessage(
  'What about weekly cleaning?',
  firstResponse.session_id
);
console.log(secondResponse.message);
```

### cURL Example

```bash
# Send a message
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are your cleaning service prices?"
  }'

# Continue conversation with session ID
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What about weekly cleaning?",
    "session_id": "api_session_abc123"
  }'

# Get session history
curl -X GET "http://localhost:8000/sessions/api_session_abc123/history"
```

## CORS

The API includes CORS middleware that allows requests from any origin by default. In production, you should configure `allow_origins` in `api.py` to specify only trusted domains.

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200 OK`: Successful request
- `400 Bad Request`: Invalid request data
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

Error responses follow this format:
```json
{
  "detail": "Error message description"
}
```

## Production Deployment

For production deployment:

1. Set environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `FACEBOOK_PAGE_ACCESS_TOKEN`: Facebook Page Access Token (for Messenger integration)
   - `FACEBOOK_VERIFY_TOKEN`: Custom token for webhook verification (for Messenger integration)
   - Configure `.env` file with required settings
   
   See `MESSENGER_SETUP.md` for detailed Messenger integration setup instructions.

2. Use a production ASGI server:
   ```bash
   uvicorn api:api_app --host 0.0.0.0 --port 8000 --workers 4
   ```

3. Use a reverse proxy (nginx, Caddy, etc.) for:
   - SSL/TLS termination
   - Rate limiting
   - Load balancing

4. Configure CORS properly:
   - Update `allow_origins` in `api.py` to your frontend domains

5. Add authentication/authorization if needed (API keys, JWT tokens, etc.)

## Support

For issues or questions, please refer to the project documentation or contact the development team.

