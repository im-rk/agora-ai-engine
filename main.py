# from src.services.llm_service import ask_llm

# if __name__ == "__main__":
#     res = ask_llm(
#         system_prompt="You are a helpful assistant",
#         user_prompt="What is AI?"
#     )
#     print(res)

# from src.services.embedding_service import get_embedding

# if __name__ == "__main__":
#     emb = get_embedding("AI improves education")
#     print(len(emb))

from fastapi import FastAPI
from src.api.rest import matches

# Create FastAPI app
app = FastAPI(
    title="Agora AI Debate Engine",
    description="AI-powered debate system with real-time agents",
    version="1.0.0"
)

# Include routers
app.include_router(matches.router, prefix="/api/v1/matches", tags=["Matches"])


# Root endpoint (health check)
@app.get("/")
def root():
    return {
        "message": "Agora AI Debate Engine is running 🚀"
    }