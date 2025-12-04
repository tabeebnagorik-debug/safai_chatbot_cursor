"""
Facebook Messenger service for sending messages via Graph API
"""
import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

# Facebook Messenger configuration
PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
GRAPH_API_URL = "https://graph.facebook.com/v21.0"


def send_message(recipient_id: str, message_text: str) -> dict:
    """
    Send a text message to a Messenger user.
    
    Args:
        recipient_id: Facebook Messenger PSID (Page-Scoped ID) of the recipient
        message_text: Text message to send
        
    Returns:
        API response as dictionary
        
    Raises:
        ValueError: If PAGE_ACCESS_TOKEN is not configured
        requests.RequestException: If API request fails
    """
    if not PAGE_ACCESS_TOKEN:
        raise ValueError("FACEBOOK_PAGE_ACCESS_TOKEN is not configured in environment variables")
    
    url = f"{GRAPH_API_URL}/me/messages"
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "messaging_type": "RESPONSE"
    }
    
    params = {"access_token": PAGE_ACCESS_TOKEN}
    
    response = requests.post(url, json=payload, params=params)
    response.raise_for_status()
    
    return response.json()


def send_typing_indicator(recipient_id: str, action: str = "typing_on") -> dict:
    """
    Send typing indicator to show the bot is typing.
    
    Args:
        recipient_id: Facebook Messenger PSID of the recipient
        action: "typing_on" or "typing_off"
        
    Returns:
        API response as dictionary
        
    Raises:
        ValueError: If PAGE_ACCESS_TOKEN is not configured
        requests.RequestException: If API request fails
    """
    if not PAGE_ACCESS_TOKEN:
        raise ValueError("FACEBOOK_PAGE_ACCESS_TOKEN is not configured in environment variables")
    
    url = f"{GRAPH_API_URL}/me/messages"
    
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": action
    }
    
    params = {"access_token": PAGE_ACCESS_TOKEN}
    
    response = requests.post(url, json=payload, params=params)
    response.raise_for_status()
    
    return response.json()


def get_user_profile(psid: str) -> Optional[dict]:
    """
    Get user profile information from Facebook.
    
    Args:
        psid: Facebook Messenger PSID
        
    Returns:
        User profile dictionary or None if failed
    """
    if not PAGE_ACCESS_TOKEN:
        return None
    
    url = f"{GRAPH_API_URL}/{psid}"
    
    params = {
        "fields": "first_name,last_name,profile_pic",
        "access_token": PAGE_ACCESS_TOKEN
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None
