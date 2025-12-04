"""
Facebook Messenger webhook router for handling incoming messages
"""
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
from safai_rag_langgraph import app as langgraph_app
from langchain_core.messages import AIMessage
from services.messenger_service import send_message, send_typing_indicator
import os
from dotenv import load_dotenv
import logging

load_dotenv(dotenv_path=".env", override=True)

logger = logging.getLogger(__name__)

router = APIRouter()

# Facebook webhook verification token
VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "")


@router.get("/webhook/messenger")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    """
    Facebook webhook verification endpoint.
    
    Facebook will call this endpoint during webhook setup to verify ownership.
    """
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(content=challenge, status_code=200)
    else:
        logger.warning(f"Webhook verification failed: mode={mode}, token matches={token == VERIFY_TOKEN}")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/messenger")
async def handle_webhook(request: Request):
    """
    Handle incoming Facebook Messenger webhook events.
    
    Processes messages from Messenger and sends responses back via the AI agent.
    """
    try:
        body = await request.json()
        
        # Facebook sends events in a specific format
        if body.get("object") != "page":
            return {"status": "ignored", "reason": "not a page event"}
        
        entries = body.get("entry", [])
        
        for entry in entries:
            messaging_events = entry.get("messaging", [])
            
            for event in messaging_events:
                # Skip if not a message event
                if "message" not in event:
                    continue
                
                # Get sender PSID
                sender_psid = event.get("sender", {}).get("id")
                if not sender_psid:
                    logger.warning("No sender PSID found in event")
                    continue
                
                # Get message text
                message = event.get("message", {})
                message_text = message.get("text")
                
                # Skip if message has no text (e.g., attachments, quick replies)
                if not message_text:
                    logger.info(f"Received non-text message from {sender_psid}")
                    continue
                
                # Check if message is an echo (sent by our page)
                if message.get("is_echo"):
                    logger.info(f"Ignoring echo message from {sender_psid}")
                    continue
                
                # Process the message asynchronously
                # We return 200 OK immediately to acknowledge receipt
                # and process the message in the background
                try:
                    await process_message(sender_psid, message_text)
                except Exception as e:
                    logger.error(f"Error processing message from {sender_psid}: {str(e)}")
        
        # Always return 200 OK to acknowledge webhook receipt
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        # Still return 200 to prevent Facebook from retrying
        return {"status": "error", "message": str(e)}


async def process_message(psid: str, message_text: str):
    """
    Process an incoming message from Messenger using LangGraph.
    
    Args:
        psid: Facebook Messenger Page-Scoped ID
        message_text: The message text from the user
    """
    try:
        # Send typing indicator
        send_typing_indicator(psid, "typing_on")
        
        # Use PSID as thread_id for LangGraph conversation state
        thread_id = f"messenger_{psid}"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Get current state from checkpoint to preserve existing messages
        current_state = langgraph_app.get_state(config)
        state_values = current_state.values if current_state.values else {}
        existing_messages = state_values.get("messages", [])
        
        # Create initial state with the new question and existing messages
        initial_state = {
            "messages": existing_messages,
            "question": message_text,
            "context": ""
        }
        
        # Invoke the graph - checkpointing will persist the updated state
        result = langgraph_app.invoke(initial_state, config)
        
        # Extract AI response
        ai_response = extract_ai_response(result)
        
        # Turn off typing indicator
        send_typing_indicator(psid, "typing_off")
        
        # Send response back to user
        send_message(psid, ai_response)
        
        logger.info(f"Successfully processed message from {psid}")
        
    except Exception as e:
        logger.error(f"Error in process_message for {psid}: {str(e)}")
        # Send error message to user
        try:
            send_typing_indicator(psid, "typing_off")
            send_message(psid, "Sorry, I encountered an error processing your message. Please try again.")
        except Exception as send_error:
            logger.error(f"Error sending error message to {psid}: {str(send_error)}")
        raise


def extract_ai_response(result: dict) -> str:
    """
    Extract AI response from LangGraph result.
    
    Args:
        result: Result dictionary from langgraph_app.invoke()
        
    Returns:
        AI response text
    """
    messages = result.get("messages", [])
    if not messages:
        return "Sorry, I couldn't generate a response. Please try again."
    
    # Find the last AI message
    ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
    if ai_messages:
        return ai_messages[-1].content
    else:
        # Fallback: get last message content
        return messages[-1].content

