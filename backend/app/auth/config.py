"""
Supabase Configuration and Client
"""

import os
from supabase import create_client, Client
from functools import lru_cache

# Load from environment
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


@lru_cache()
def get_supabase_client() -> Client:
    """Get cached Supabase client with service role (admin) access."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("Supabase credentials not configured")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_jwt_secret() -> str:
    """Get JWT secret for token verification."""
    return SUPABASE_JWT_SECRET
