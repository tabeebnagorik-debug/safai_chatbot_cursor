from sqlalchemy.orm import Session
from models import User
from utils.phone_validator import normalize_phone
from typing import Optional
import uuid


def get_or_create_user(db: Session, phone_number: str) -> User:
    """
    Get existing user by phone number or create a new one.
    
    Args:
        db: Database session
        phone_number: Phone number to lookup/create
        
    Returns:
        User object
    """
    # Normalize phone number
    normalized_phone = normalize_phone(phone_number)
    
    # Try to get existing user
    user = db.query(User).filter(User.phone_number == normalized_phone).first()
    
    if user:
        return user
    
    # Create new user
    user = User(
        id=uuid.uuid4(),
        phone_number=normalized_phone
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


def get_user_by_phone(db: Session, phone_number: str) -> Optional[User]:
    """
    Get user by phone number.
    
    Args:
        db: Database session
        phone_number: Phone number to lookup
        
    Returns:
        User object or None if not found
    """
    normalized_phone = normalize_phone(phone_number)
    return db.query(User).filter(User.phone_number == normalized_phone).first()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[User]:
    """
    Get user by ID.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        User object or None if not found
    """
    return db.query(User).filter(User.id == user_id).first()

