# Agora AI Engine

A Python-based AI engine built with FastAPI, LangChain, and gRPC.

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/im-rk/agora-ai-engine.git
   cd agora-ai-engine
   ```

2. **Install uv** (if not already installed)
   ```bash
   # On macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```
   This will create a virtual environment and install all dependencies from `uv.lock`.

4. **Run the project**
   ```bash
   uv run python main.py
   ```

## Dependencies

This project uses:
- FastAPI - Web framework
- LangChain & LangChain-OpenAI - LLM orchestration
- gRPC - Remote procedure calls
- Pinecone - Vector database
- Redis - Caching
- Pydantic - Data validation
- Uvicorn - ASGI server

## Development

To add new dependencies:
```bash
uv add <package-name>
```

To run scripts with uv:
```bash
uv run <script-name>
```
