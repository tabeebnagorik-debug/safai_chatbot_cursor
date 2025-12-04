from sqlalchemy.orm import Session
from models import ChatSession, User
from typing import Optional, List
from datetime import datetime
import uuid


def deactivate_user_sessions(db: Session, user_id: uuid.UUID) -> int:
    """
    Deactivate all active sessions for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Number of sessions deactivated
    """
    count = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.is_active == True
    ).update({"is_active": False, "updated_at": datetime.utcnow()})
    
    db.commit()
    return count


def create_session(db: Session, user_id: uuid.UUID) -> ChatSession:
    """
    Create a new active session for a user.
    Deactivates any existing active sessions first.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Created ChatSession object
    """
    # Deactivate existing active sessions
    deactivate_user_sessions(db, user_id)
    
    # Create new session
    session = ChatSession(
        id=uuid.uuid4(),
        user_id=user_id,
        is_active=True,
        last_message_at=None
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return session


def get_session(db: Session, session_id: uuid.UUID) -> Optional[ChatSession]:
    """
    Get session by ID.
    
    Args:
        db: Database session
        session_id: Session UUID
        
    Returns:
        ChatSession object or None if not found
    """
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_active_session(db: Session, session_id: uuid.UUID) -> Optional[ChatSession]:
    """
    Get active session by ID.
    
    Args:
        db: Database session
        session_id: Session UUID
        
    Returns:
        Active ChatSession object or None if not found or not active
    """
    return db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.is_active == True
    ).first()


def update_session_last_message(db: Session, session_id: uuid.UUID) -> None:
    """
    Update the last_message_at timestamp for a session.
    
    Args:
        db: Database session
        session_id: Session UUID
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.commit()


def get_user_sessions(db: Session, user_id: uuid.UUID, active_only: bool = False) -> List[ChatSession]:
    """
    Get all sessions for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        active_only: If True, only return active sessions
        
    Returns:
        List of ChatSession objects
    """
    query = db.query(ChatSession).filter(ChatSession.user_id == user_id)
    
    if active_only:
        query = query.filter(ChatSession.is_active == True)
    
    return query.order_by(ChatSession.created_at.desc()).all()


def get_or_create_active_session(db: Session, user_id: uuid.UUID) -> ChatSession:
    """
    Get existing active session for a user, or create a new one if none exists.
    This preserves chat history by reusing the same session_id.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Active ChatSession object (existing or newly created)
    """
    # Check if user has an active session
    active_sessions = get_user_sessions(db, user_id, active_only=True)
    
    if active_sessions:
        # Return the most recent active session (to maintain chat history)
        return active_sessions[0]
    
    # No active session found, create a new one
    return create_session(db, user_id)

