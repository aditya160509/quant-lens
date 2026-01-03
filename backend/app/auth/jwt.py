"""
JWT Token Verification for Supabase
"""

from jose import jwt, JWTError
from typing import Optional, Dict, Any
from datetime import datetime
import os

# Supabase uses HS256 by default
ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    """Get JWT secret from environment."""
    return os.getenv("SUPABASE_JWT_SECRET", "")


def verify_token(token: str) -> bool:
    """Verify if a token is valid."""
    try:
        secret = get_jwt_secret()
        jwt.decode(token, secret, algorithms=[ALGORITHM], audience="authenticated")
        return True
    except JWTError:
        return False


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and return token payload."""
    try:
        secret = get_jwt_secret()
        payload = jwt.decode(
            token, 
            secret, 
            algorithms=[ALGORITHM],
            audience="authenticated"
        )
        return payload
    except JWTError as e:
        print(f"JWT decode error: {e}")
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """Extract user ID (sub) from token."""
    payload = decode_token(token)
    if payload:
        return payload.get("sub")
    return None


def get_user_email_from_token(token: str) -> Optional[str]:
    """Extract user email from token."""
    payload = decode_token(token)
    if payload:
        return payload.get("email")
    return None


def is_token_expired(token: str) -> bool:
    """Check if token is expired."""
    payload = decode_token(token)
    if not payload:
        return True
    
    exp = payload.get("exp")
    if not exp:
        return True
    
    return datetime.utcnow().timestamp() > exp
