"""
Agora AI Debate Engine - Main Application

FastAPI application for AI-powered parliamentary debate.

Current implementation:
- Authentication: Supabase (frontend) + JWT (backend)
- Only endpoint: POST /api/auth/verify-supabase
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging

from src.api.routes.v1 import v1_router
from src.workers.redis_consumer import start_redis_consumer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    
    Startup:
    - Start Redis consumer for debate events
    
    Shutdown:
    - Cancel Redis consumer
    """
    logger.info("Starting Agora AI Debate Engine...")
    
    # Start background worker
    worker_task = asyncio.create_task(start_redis_consumer())
    
    logger.info("Application started successfully")
    
    yield
    
    logger.info("Shutting down...")
    worker_task.cancel()
    logger.info("Application shut down")


# Create FastAPI app
app = FastAPI(
    title="Agora AI Debate Engine",
    description="AI-powered parliamentary debate system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# ============ MIDDLEWARE ============

# Add CORS middleware
# Disabled because the Go Gateway at port 8080 specifically handles all CORS preflight and headers.
# Double-stacking them will cause 'TypeError: Failed to fetch' on the frontend.

# ============ ROUTES ============

# Include v1 router
app.include_router(v1_router)

# ============ HEALTH CHECK ============

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Agora AI Debate Engine is running",
        "version": "1.0.0"
    }
