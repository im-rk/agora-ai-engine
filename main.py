from fastapi import FastAPI
from src.api.rest import matches


app = FastAPI(
    title="Agora AI Debate Engine",
    description="AI-powered debate system with real-time agents",
    version="1.0.0"
)


app.include_router(matches.router, prefix="/matches", tags=["Matches"])



@app.get("/")
def root():
    return {
        "message": "Agora AI Debate Engine is running "
    }