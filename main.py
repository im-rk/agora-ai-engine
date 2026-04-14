from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from src.api.rest import matches
from src.workers.redis_consumer import start_redis_consumer
from src.api.rest import matches, history


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"], # This explicitly allows the OPTIONS method
    allow_headers=["*"],
)

# Include routers
app.include_router(matches.router, prefix="/api/v1/matches", tags=["Matches"])
app.include_router(history.router, prefix="/api/v1/debates", tags=["Results"])


@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "Agora AI Debate Engine is running"}