from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    
    Why Pydantic Settings?
    - Automatic validation: if VAPI_API_KEY is missing, the app fails loudly at startup
    - Type safety: we know API_URL is a string, not randomly a number
    - .env file support: loads from .env automatically
    """

    # VAPI Configuration
    VAPI_API_KEY: str
    """
    Your VAPI API key for authenticating webhook calls.
    Get this from: https://dashboard.vapi.ai/settings
    Why we need it: VAPI sends webhook events with a signature we verify.
    """

    VAPI_PRIVATE_KEY: str
    """
    Your VAPI private key for verifying webhook authenticity.
    Same place as API_KEY in VAPI dashboard.
    Why: Prevents fake webhook calls from malicious actors.
    """

    # Supabase Configuration
    SUPABASE_URL: str
    """
    Your Supabase project URL.
    Format: https://[project-id].supabase.co
    Get this from: Supabase dashboard → Settings → API
    Why: This is the database endpoint we connect to.
    """

    SUPABASE_KEY: str
    """
    Your Supabase anon/service role key.
    Get this from: Supabase dashboard → Settings → API
    Why: Authentication token for database queries.
    """

    SUPABASE_DB_PASSWORD: Optional[str] = None
    """
    Supabase database password for direct PostgreSQL connections (optional).
    Only needed if using raw SQL; we'll use the HTTP API so this stays None.
    """

    # Application Configuration
    APP_NAME: str = "nova-backend"
    """
    Just a friendly name for logging and identification.
    """

    ENVIRONMENT: str = "development"
    """
    Either 'development' or 'production'.
    Controls logging level and error verbosity.
    """

    LOG_LEVEL: str = "INFO"
    """
    Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    Use DEBUG locally, INFO in production.
    """

    # Railway/Deployment
    PORT: int = 8000
    """
    Port the FastAPI server runs on.
    Railway sets this via environment variable; local dev uses 8000.
    """

    class Config:
        """
        Pydantic Settings config.
        
        env_file tells it to load from .env file.
        This is why we can run locally with a .env file, and Railway
        uses environment variables without touching the code.
        """
        env_file = ".env"
        case_sensitive = True


# Create a global settings instance
# We'll import this in other files: from app.config import settings
settings = Settings()