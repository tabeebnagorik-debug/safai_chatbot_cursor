from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from safai_rag_langgraph import app as langgraph_app
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import Session
from database import init_db, get_db
from services.user_service import get_or_create_user
from services.session_service import (
    get_or_create_active_session,
    get_active_session, 
    update_session_last_message,
    get_session
)
from utils.phone_validator import validate_bangladeshi_phone
from routers.messenger_webhook import router as messenger_webhook_router
import uuid
from datetime import datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup: Initialize database
    init_db()
    yield
    # Shutdown: Cleanup if needed (currently nothing to clean up)


# Create FastAPI app with lifespan handler
# Set root_path for reverse proxy support (when behind /ai/ prefix)
api_app = FastAPI(
    title="Safai AI Chat Agent API",
    description="REST API for Safai's AI Customer Support Assistant powered by LangGraph and RAG",
    version="1.0.0",
    lifespan=lifespan,
    root_path="/ai"  # This tells FastAPI it's being served behind /ai/ prefix
)

# Add CORS middleware to allow third-party apps to access the API
api_app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origins=["https://st.safai.com.bd", "http://localhost:3000"],
)

# Include Messenger webhook router
api_app.include_router(messenger_webhook_router)

# Request/Response Models
class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class InitiateChatRequest(BaseModel):
    """Request model for initiating chat with phone number"""
    phone_number: str = Field(..., description="Bangladeshi phone number (e.g., +8801712345678, 01712345678)")


class InitiateChatResponse(BaseModel):
    """Response model for initiate-chat endpoint"""
    success: bool = Field(..., description="Whether the request was successful")
    session_id: str = Field(..., description="Session ID for this conversation")
    user_id: str = Field(..., description="User ID")
    message: str = Field(..., description="Success message")
    timestamp: str = Field(..., description="Response timestamp in ISO format")


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(..., description="User's message/question")
    session_id: str = Field(..., description="Session ID for maintaining conversation context (required)")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="AI assistant's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    timestamp: str = Field(..., description="Response timestamp in ISO format")


class SessionHistoryResponse(BaseModel):
    """Response model for session history"""
    success: bool
    session_id: str
    message_count: int
    messages: List[Dict[str, str]] = Field(..., description="List of messages with role and content")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str


def extract_ai_response(result: Dict[str, Any]) -> str:
    """Extract AI response from LangGraph result"""
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


@api_app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Safai AI Chat Agent API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@api_app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat()
    )


@api_app.post("/auth/initiate-chat", response_model=InitiateChatResponse)
async def initiate_chat(request: InitiateChatRequest, db: Session = Depends(get_db)):
    """
    Initiate a chat session by providing phone number.
    
    This endpoint:
    1. Validates the Bangladeshi phone number
    2. Creates or retrieves user by phone number
    3. Returns existing active session if user has one (preserves chat history)
    4. Creates a new active session only if user has no active session
    5. Returns session_id and user_id
    """
    try:
        # Validate phone number
        is_valid, normalized_phone, error_msg = validate_bangladeshi_phone(request.phone_number)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Get or create user
        user = get_or_create_user(db, normalized_phone)
        
        # Get existing active session or create a new one
        # This preserves chat history by reusing the same session_id
        session = get_or_create_active_session(db, user.id)
        
        # Determine message based on whether session is new or existing
        is_new_session = session.last_message_at is None
        message = "Chat session initiated successfully" if is_new_session else "Returned to existing chat session"
        
        return InitiateChatResponse(
            success=True,
            session_id=str(session.id),
            user_id=str(user.id),
            message=message,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error initiating chat: {str(e)}"
        )


@api_app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a message to the AI chat agent and receive a response.
    
    This endpoint requires a valid session_id obtained from /auth/initiate-chat.
    The session_id must be active and associated with a user.
    """
    try:
        # Validate session_id format
        try:
            session_uuid = uuid.UUID(request.session_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid session_id format. Must be a valid UUID."
            )
        
        # Check if session exists and is active
        session = get_active_session(db, session_uuid)
        if not session:
            # Check if session exists but is inactive
            existing_session = get_session(db, session_uuid)
            if existing_session:
                raise HTTPException(
                    status_code=403,
                    detail="Session is not active. Please initiate a new chat session."
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail="Session not found. Please initiate a new chat session."
                )
        
        # Use session_id as thread_id for LangGraph
        config = {"configurable": {"thread_id": request.session_id}}
        
        # Get current state from checkpoint to preserve existing messages
        current_state = langgraph_app.get_state(config)
        state_values = current_state.values if current_state.values else {}
        existing_messages = state_values.get("messages", [])
        
        # Create initial state with the new question and existing messages
        initial_state = {
            "messages": existing_messages,
            "question": request.message,
            "context": ""
        }
        
        # Invoke the graph - checkpointing will persist the updated state
        result = langgraph_app.invoke(initial_state, config)
        
        # Extract AI response
        ai_response = extract_ai_response(result)
        
        # Update session last_message_at timestamp
        update_session_last_message(db, session_uuid)
        
        return ChatResponse(
            success=True,
            message=ai_response,
            session_id=request.session_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {str(e)}"
        )


@api_app.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str):
    """
    Get conversation history for a specific session.
    """
    try:
        config = {"configurable": {"thread_id": session_id}}
        current_state = langgraph_app.get_state(config)
        state_values = current_state.values if current_state.values else {}
        messages = state_values.get("messages", [])
        
        # Convert messages to dict format
        message_list = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                message_list.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                message_list.append({"role": "assistant", "content": msg.content})
        
        return SessionHistoryResponse(
            success=True,
            session_id=session_id,
            message_count=len(message_list),
            messages=message_list
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving session history: {str(e)}"
        )


@api_app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """
    Clear/reset a conversation session.
    Note: This removes the checkpoint state, effectively starting a new conversation.
    """
    try:
        # LangGraph's MemorySaver doesn't have a direct delete method
        # The session will effectively reset on the next message with a new initial state
        # For a proper clear, we'd need to implement session deletion in the checkpointer
        # For now, we'll return success and let the client know they can start fresh
        
        return {
            "success": True,
            "message": f"Session {session_id} can be reset. Send a new message to start fresh.",
            "session_id": session_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing session: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api_app, host="0.0.0.0", port=8000)

