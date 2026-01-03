"""
FastAPI Dependencies for Authentication
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from pydantic import BaseModel

from .jwt import decode_token, verify_token


# Security scheme for Swagger UI
security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """Current authenticated user model."""
    id: str
    email: Optional[str] = None
    role: str = "authenticated"
    
    class Config:
        extra = "allow"  # Allow additional fields from token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> CurrentUser:
    """
    Dependency to get current authenticated user.
    Raises 401 if not authenticated.
    
    Usage:
        @router.get("/protected")
        def protected_route(user: CurrentUser = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    
    if not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return CurrentUser(
        id=payload.get("sub", ""),
        email=payload.get("email"),
        role=payload.get("role", "authenticated")
    )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[CurrentUser]:
    """
    Dependency to optionally get current user.
    Returns None if not authenticated (doesn't raise error).
    
    Usage:
        @router.get("/public-or-private")
        def mixed_route(user: Optional[CurrentUser] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello anonymous"}
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    
    if not verify_token(token):
        return None
    
    payload = decode_token(token)
    
    if not payload:
        return None
    
    return CurrentUser(
        id=payload.get("sub", ""),
        email=payload.get("email"),
        role=payload.get("role", "authenticated")
    )
