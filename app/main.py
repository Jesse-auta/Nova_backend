import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

"""
Why separate config into its own file?
- Keeps main.py focused on app setup
- Settings are centralized and testable
- Easy to swap between dev/prod configs
"""

# ============================================================================
# LOGGING SETUP
# ============================================================================
# Configure logging so we can see what's happening in the console and in prod

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

"""
Why logging.basicConfig()?
- Tells Python's logging module how to format messages
- level=settings.LOG_LEVEL means respect our environment variable
- format shows timestamp, logger name, level (DEBUG/INFO/ERROR), and the message
- We'll use 'logger' throughout the app to log important events

Example log output:
2024-01-15 10:23:45,123 - app.main - INFO - Application started
"""

# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="AI receptionist backend for handling VAPI webhooks",
    version="1.0.0"
)

"""
Why FastAPI?
- Built-in automatic API documentation (Swagger UI)
- Type hints = automatic validation
- Async/await support for high concurrency
- Fast (very minimal overhead)

The title/description/version show up in /docs (interactive API docs)
"""

# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now (fine for testing, tighten in prod)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
Why CORS middleware?
- Prevents browsers from blocking cross-origin requests
- allow_origins=["*"] means any domain can call our API
- In production, change this to specific domains: allow_origins=["https://yourdomain.com"]
- This protects against unwanted requests

Example: Without CORS, a frontend at domain-a.com calling domain-b.com would be blocked by the browser
"""

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    
    Why we need this:
    - Railway and other deployment platforms ping /health to verify the app is running
    - If this fails, Railway auto-restarts the app
    - We can log this to make sure the app is alive
    
    Returns:
    {
        "status": "ok",
        "app_name": "nova-backend",
        "environment": "development"
    }
    """
    logger.info("Health check pinged")
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT
    }

"""
Why async?
- Allows FastAPI to handle multiple requests concurrently
- Python's async/await is built for I/O-bound work (database queries, API calls)
- Without async, each request blocks until it's done
- With async, we can handle 100 requests with minimal threads

The @app.get() decorator:
- Routes GET requests to /health to this function
- Returns JSON automatically
"""

# ============================================================================
# API ROUTES
# ============================================================================


from app.api.v1 import webhooks
app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])

"""
Why include_router() and prefix="/api/v1"?
- Keeps routes modular (each feature in its own file)
- prefix means all routes in webhooks.py start with /api/v1
- So a route @app.get("/webhook") becomes GET /api/v1/webhook
- This makes versioning easy (when v2 comes, we add a new router with prefix="/api/v2")

We'll uncomment this once we build webhooks.py
"""

# ============================================================================
# APP STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Runs when the app starts up.
    
    Why use startup events?
    - Initialize database connections
    - Load caches
    - Log that the app is starting
    - Do expensive operations once, not on every request
    """
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode")
    logger.info(f"Logging level: {settings.LOG_LEVEL}")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs when the app shuts down gracefully.
    
    Why use shutdown events?
    - Close database connections properly
    - Flush logs
    - Clean up resources
    """
    logger.info(f"Shutting down {settings.APP_NAME}")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    This runs when you do: python -m app.main
    or: python app/main.py
    
    We use uvicorn (async ASGI server) to run FastAPI
    host="0.0.0.0" means listen on all network interfaces
    port is from environment variable
    reload=True auto-reloads when you save (dev only, not for production)
    """
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development"
    )