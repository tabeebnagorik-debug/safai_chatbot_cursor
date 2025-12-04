# Facebook Messenger Integration Setup

This guide explains how to set up and configure the Facebook Messenger webhook integration for the Safai AI Chat Agent.

## Overview

The Messenger integration allows users to chat with the AI agent directly through Facebook Messenger. The integration uses webhooks to receive messages and the Facebook Graph API to send responses.

## Prerequisites

1. A Facebook Page (create one at [facebook.com/pages/create](https://www.facebook.com/pages/create))
2. A Facebook App (create one at [developers.facebook.com](https://developers.facebook.com))
3. Access to your server's public URL (for webhook configuration)

## Step 1: Create a Facebook App

1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Click "My Apps" → "Create App"
3. Select "Business" as the app type
4. Fill in your app details and create the app

## Step 2: Add Messenger Product

1. In your Facebook App dashboard, go to "Add Product"
2. Find "Messenger" and click "Set Up"
3. This will add Messenger to your app

## Step 3: Generate Page Access Token

1. In the Messenger settings, go to "Access Tokens" section
2. Select your Facebook Page from the dropdown
3. Click "Generate Token"
4. Copy the generated Page Access Token (you'll need this for your `.env` file)

## Step 4: Configure Webhook

1. In the Messenger settings, scroll to "Webhooks" section
2. Click "Add Callback URL"
3. Enter your webhook URL:
   ```
   https://your-domain.com/webhook/messenger
   ```
   Note: If your API is behind a reverse proxy with a prefix (e.g., `/ai`), the URL should be:
   ```
   https://your-domain.com/ai/webhook/messenger
   ```
4. Enter a Verify Token (create a random secure string, e.g., `your_secure_verify_token_12345`)
5. Click "Verify and Save"

## Step 5: Subscribe to Page Events

1. After webhook is verified, click "Edit" next to your webhook
2. In "Subscription Fields", subscribe to:
   - `messages`
   - `messaging_postbacks` (optional, if you want to handle postbacks)
3. Click "Save"

## Step 6: Configure Environment Variables

Add the following variables to your `.env` file:

```env
# Facebook Messenger Configuration
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token_here
FACEBOOK_VERIFY_TOKEN=your_verify_token_here
```

**Important Security Notes:**
- Never commit your `.env` file to version control
- Use a strong, random verify token
- Keep your Page Access Token secure

## Step 7: Deploy and Test

1. Ensure your server is running and accessible at the webhook URL
2. Send a test message to your Facebook Page from Messenger
3. The AI agent should respond automatically

## Webhook Endpoints

### GET `/webhook/messenger`
- **Purpose:** Webhook verification (called by Facebook during setup)
- **Parameters:**
  - `hub.mode`: Should be "subscribe"
  - `hub.verify_token`: Must match `FACEBOOK_VERIFY_TOKEN`
  - `hub.challenge`: Random string from Facebook
- **Response:** Returns the challenge string if verification succeeds

### POST `/webhook/messenger`
- **Purpose:** Receive incoming messages from Messenger
- **Request Body:** JSON payload from Facebook Messenger webhook
- **Response:** Always returns `{"status": "ok"}` with 200 status code

## How It Works

1. User sends a message on Facebook Messenger to your Page
2. Facebook sends a webhook POST request to `/webhook/messenger`
3. The webhook handler extracts the message text and sender PSID
4. The message is processed using LangGraph with thread_id = `messenger_{psid}`
5. The AI generates a response
6. The response is sent back to the user via Facebook Graph API
7. Conversation history is maintained per PSID using LangGraph checkpoints

## Conversation State

- Each Messenger user (identified by PSID) has their own conversation thread
- Conversation history is automatically maintained using LangGraph's checkpointing system
- No database user management is required for Messenger users
- Thread IDs are formatted as: `messenger_{psid}`

## Troubleshooting

### Webhook Verification Fails
- Check that `FACEBOOK_VERIFY_TOKEN` matches the token you entered in Facebook
- Ensure your server is publicly accessible
- Check server logs for errors

### Messages Not Received
- Verify webhook is subscribed to `messages` event
- Check that your Page Access Token is valid
- Ensure your server is running and accessible
- Check server logs for incoming webhook requests

### Messages Not Sending
- Verify `FACEBOOK_PAGE_ACCESS_TOKEN` is correct
- Check that the token has `pages_messaging` permission
- Ensure the token hasn't expired
- Check server logs for API errors

### Testing Locally
For local development, use a tool like [ngrok](https://ngrok.com/) to expose your local server:
```bash
ngrok http 8000
```
Then use the ngrok URL in your Facebook webhook configuration.

## Security Considerations

1. **HTTPS Required:** Facebook requires webhooks to use HTTPS in production
2. **Verify Token:** Always use a strong, random verify token
3. **Access Token:** Keep your Page Access Token secure and rotate it periodically
4. **Rate Limiting:** Consider implementing rate limiting for webhook endpoints
5. **Input Validation:** The webhook handler validates incoming requests, but be aware of Facebook's webhook format

## Additional Resources

- [Facebook Messenger Platform Documentation](https://developers.facebook.com/docs/messenger-platform)
- [Facebook Graph API Documentation](https://developers.facebook.com/docs/graph-api)
- [Webhook Reference](https://developers.facebook.com/docs/messenger-platform/webhook)

