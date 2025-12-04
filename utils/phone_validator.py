import re
from typing import Tuple, Optional


def validate_bangladeshi_phone(phone_number: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and normalize Bangladeshi phone numbers.
    
    Args:
        phone_number: Phone number to validate
        
    Returns:
        Tuple of (is_valid, normalized_phone, error_message)
        - is_valid: True if phone number is valid
        - normalized_phone: Normalized phone number in format +880XXXXXXXXX or None if invalid
        - error_message: Error message if invalid, None if valid
    """
    # Remove all whitespace
    phone = phone_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Pattern for Bangladeshi mobile numbers
    # Valid formats:
    # - +8801712345678 (with country code and +)
    # - 8801712345678 (with country code, no +)
    # - 01712345678 (local format, starts with 0)
    # Mobile prefixes: 013, 014, 015, 016, 017, 018, 019
    
    # Check for +880 format (13 digits total)
    pattern_plus = re.compile(r'^\+8801[3-9]\d{8}$')
    # Check for 880 format without + (12 digits)
    pattern_880 = re.compile(r'^8801[3-9]\d{8}$')
    # Check for local format starting with 0 (11 digits)
    pattern_local = re.compile(r'^01[3-9]\d{8}$')
    
    if pattern_plus.match(phone):
        # Already in correct format
        return True, phone, None
    elif pattern_880.match(phone):
        # Add + prefix
        normalized = f"+{phone}"
        return True, normalized, None
    elif pattern_local.match(phone):
        # Convert local format to international
        # Remove leading 0, add +880
        normalized = f"+880{phone[1:]}"
        return True, normalized, None
    else:
        # Invalid format
        error_msg = (
            "Invalid Bangladeshi phone number format. "
            "Valid formats: +8801712345678, 8801712345678, or 01712345678. "
            "Mobile prefixes: 013-019"
        )
        return False, None, error_msg


def normalize_phone(phone_number: str) -> str:
    """
    Normalize phone number to standard format (+880XXXXXXXXX).
    Raises ValueError if phone number is invalid.
    """
    is_valid, normalized, error = validate_bangladeshi_phone(phone_number)
    if not is_valid:
        raise ValueError(error)
    return normalized

