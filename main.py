from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from src.api.rest import matches
from src.workers.redis_consumer import start_redis_consumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup and shutdown."""
    worker_task = asyncio.create_task(start_redis_consumer())
    yield
    worker_task.cancel()


# Create FastAPI app
app = FastAPI(
    title="Agora AI Debate Engine",
    description="AI-powered debate system with real-time agents",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(matches.router, prefix="/api/v1/matches", tags=["Matches"])


@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Agora AI Debate Engine is running"}