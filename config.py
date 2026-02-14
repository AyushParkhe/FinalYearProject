# config.py
import os

class Config:
    """
    Central configuration class.
    Loaded once at app startup.
    """

    # Flask
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Supabase / Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Supabase JWT
    # SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

    # Basic sanity checks (fail fast)
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")

    # if not SUPABASE_JWT_SECRET:
    #     raise RuntimeError("SUPABASE_JWT_SECRET is not set")
