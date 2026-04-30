# Agora AI Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.95+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/postgres-14+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/redis-7+-red.svg)](https://redis.io/)

A production-grade AI debate orchestration engine that powers real-time competitive debate simulations. The system intelligently generates AI speeches, manages debate state, measures performance metrics, and provides adjudication feedback through a modular, format-aware architecture.

## 🎯 Mission

Enable users to practice debate against AI opponents that adapt to their skill level, providing real-time feedback and comprehensive performance analysis across multiple debate formats.

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Core Workflows](#core-workflows)
- [Debate Formats](#debate-formats)
- [Difficulty System](#difficulty-system)
- [API Reference](#api-reference)
- [Development](#development)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│              (Audio I/O, Speech Playback Control)              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Gateway (Go) + gRPC                           │
│         (State Management, Event Coordination)                 │
└──────────────┬──────────────────────────┬──────────────────────┘
               │ Redis Pub/Sub                │ HTTP/REST
               ↓                              ↓
        ┌──────────────────┐      ┌────────────────────┐
        │ Python AI Engine │      │ PostgreSQL + Alembic
        │  (This Repo)     │      │   (Persistence)    │
        └──────────────────┘      └────────────────────┘
               │
        ┌──────┴──────────────────┐
        │                         │
        ↓                         ↓
   ┌─────────────┐         ┌─────────────┐
   │ Debater     │         │ Adjudicator │
   │ Agent (4x)  │         │ Agent       │
   └─────────────┘         └─────────────┘
        │                        │
        ↓                        ↓
   ┌─────────────────────────────────────┐
   │   External LLM Services             │
   │  ├─ Groq (Primary)                  │
   │  ├─ Cohere (RAG)                    │
   │  └─ ElevenLabs (TTS)                │
   └─────────────────────────────────────┘
```

### Data Flow

**Live Debate Turn:**
1. **START_MATCH** → Determine first speaker
2. **AI Turn** → 4-phase generation pipeline
   - State parsing → Query synthesis → Evidence retrieval → Response generation
3. **TURN_CHANGED** (via WebSocket + timing data) → Persist turn + measure duration
4. **TURN_CHANGED** → Check if next speaker is AI or Human
5. **Repeat** until all speakers complete
6. **Match completion** → Trigger adjudication
7. **ADJUDICATION** → Grade all speakers, persist results

---

## ✨ Key Features

### 1. **Format-Aware Debate Orchestration**
- **Asian Parliamentary (AP)**: 6 speakers (3 per side), 7-minute speeches
- **British Parliamentary (BP)**: 8 speakers (4 per side), 8-minute speeches
- Dynamic speaker scheduling and role constraints
- Format-specific prompt injection and evidence filters

### 2. **4-Phase AI Debate Pipeline**
```
Phase 1: State Tracking
├─ Parse debate transcript
├─ Identify clash matrix (points of disagreement)
└─ Determine strategic priorities

Phase 2: Query Synthesis
├─ Generate targeted search queries (difficulty-throttled)
├─ Leverage clash matrix for relevance
└─ Limit query count by skill level (1/2/4 queries)

Phase 3: Evidence Retrieval & Ranking
├─ Semantic search on case-prep embeddings
├─ Re-rank by match context
└─ Return top-k results (1/3/5 by difficulty)

Phase 4: Response Generation
├─ Stream LLM output via Redis callbacks
├─ Inject personality/difficulty modifiers
├─ Enforce role-specific constraints
└─ Persist to database
```

### 3. **Skill-Based Difficulty System**
Three independent levers for seamless difficulty scaling:

| Difficulty | Info Throttle | Memory Drop | Persona |
|-----------|---------------|------------|---------|
| **Beginner** | 1 query, top 1 result | 50% argument drop | 0.8 temp, novice tone |
| **Intermediate** | 2 queries, top 3 results | 10% argument drop | 0.4 temp, balanced tone |
| **Advanced** | 4 queries, top 5 results | 0% argument drop | 0.1 temp, expert tone |

**Implementation**: [src/core/difficulty.py](src/core/difficulty.py)

### 4. **Vector DB-Based RAG**
- **Storage**: PostgreSQL with pgvector extension
- **Content**: Case prep embeddings only (motion-specific arguments + counter-arguments + evidence)
- **Query**: Match-side-role-aware semantic search
- **Metadata**: match_id, user_id, side, role, motion_category

### 5. **Real-Time Event Streaming**
- Redis Pub/Sub for low-latency event coordination
- Event patterns: START_MATCH, TURN_CHANGED, MATCH_COMPLETE
- WebSocket bridge to frontend for bi-directional communication
- Async task orchestration via Python asyncio

### 6. **Accurate Speech Timing Measurement**
- Frontend captures exact audio playback duration (onplay → onended)
- Gateway forwards timing data in TURN_CHANGED event
- Python consumer persists to database
- Metrics: started_at, ended_at, duration_seconds
- **No Redis pollution**: Data travels in event payload

### 7. **Adjudication & Performance Grading**
- Evaluates all speakers on argumentation quality
- Generates detailed feedback for each role
- Scores speakers 1-10 with reasoning
- Async worker prevents debate blocking
- Results persisted for analytics

### 8. **Comprehensive Observability**
- Structured logging (LLMCallLog for all AI interactions)
- Redis state snapshots for debugging
- Turn-by-turn transcript persistence
- Performance metrics per speaker

---

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI 0.95+ (async-first)
- **Language**: Python 3.10+
- **Database**: PostgreSQL 14+ with pgvector
- **Message Queue**: Redis 7+ (Pub/Sub)
- **Async Runtime**: asyncio + aioredis
- **ORM**: SQLAlchemy 2.0

### LLM Services
- **Generation**: Groq (fast inference, streaming)
- **Embeddings**: Cohere (semantic search)
- **TTS**: ElevenLabs (natural speech synthesis)

### Deployment
- **Container**: Docker + Docker Compose
- **Orchestration**: Kubernetes (optional)
- **Database Migrations**: Alembic
- **Monitoring**: Structured logging (stdout-to-ELK)

---

## 📁 Project Structure

```
agora-ai-engine/
├── src/
│   ├── ai/                          # AI orchestration
│   │   ├── agents/
│   │   │   ├── debater.py          # 4-phase debate orchestrator
│   │   │   ├── adjudicator.py      # Grading & feedback
│   │   │   ├── prep_coach.py       # Case prep assistant
│   │   │   └── sniper.py           # Cross-ex strategist
│   │   ├── clients/
│   │   │   ├── groq_client.py      # LLM inference
│   │   │   ├── cohere_client.py    # Embeddings
│   │   │   └── openai_client.py    # Fallback LLM
│   │   ├── callbacks/
│   │   │   └── redis_stream.py     # LLM → Redis events
│   │   └── prompts/
│   │       ├── debater_prompts.py  # Debate generation
│   │       ├── adjudicator_prompts.py
│   │       └── [role-specific].py
│   │
│   ├── api/                        # REST endpoints
│   │   ├── rest/
│   │   │   ├── matches.py          # Match CRUD
│   │   │   ├── history.py          # Retrieval
│   │   │   └── users.py            # User management
│   │   └── dependencies.py         # DI + auth
│   │
│   ├── core/
│   │   ├── config.py               # Environment config
│   │   ├── database.py             # DB connection
│   │   ├── difficulty.py           # Difficulty matrix
│   │   ├── redis_client.py         # Redis helper
│   │   └── security.py             # Auth/JWT
│   │
│   ├── engine/
│   │   ├── state.py                # Live match state
│   │   └── rules.py                # Format constraints
│   │
│   ├── models/
│   │   ├── debate.py               # DebateSession, Turn
│   │   ├── user.py                 # User, SkillLevel
│   │   ├── results.py              # Grading results
│   │   └── setup.py                # Motion, CasePrep
│   │
│   ├── repositories/
│   │   ├── ap/matches.py           # AP-specific persistence
│   │   ├── bp/matches.py           # BP-specific persistence
│   │   ├── debate_repo.py          # Shared queries
│   │   ├── results_repo.py         # Grading DB ops
│   │   └── user_repo.py            # User DB ops
│   │
│   ├── schemas/
│   │   ├── debate_schema.py        # Pydantic models
│   │   ├── results_schema.py
│   │   └── user_schema.py
│   │
│   ├── services/
│   │   ├── llm_service.py          # LLM orchestration
│   │   ├── embedding_service.py    # Vector search
│   │   ├── match_service.py        # Match lifecycle
│   │   ├── grading_service.py      # Score calculation
│   │   └── user_service.py         # User logic
│   │
│   └── workers/
│       ├── redis_consumer.py       # Event listener
│       ├── ai_response_generator.py# Speech generation
│       ├── transcript_handler.py   # Transcript parsing
│       └── adjudication_worker.py  # Grading async task
│
├── alembic/
│   ├── versions/                   # DB migrations
│   ├── env.py
│   └── script.py.mako
│
├── tests/
│   ├── unit/                       # Agent/service tests
│   ├── integration/                # API/repo tests
│   └── conftest.py
│
├── main.py                         # Application entry
├── pyproject.toml                  # Dependencies
├── docker-compose.yml              # Local dev environment
└── README.md                        # This file
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (optional, recommended)

### Local Development

#### 1. Clone & Setup
```bash
git clone https://github.com/im-rk/agora-ai-engine.git
cd agora-ai-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Environment Configuration
```bash
# Copy example config
cp .env.example .env

# Edit .env with your credentials
# Required keys:
# - DATABASE_URL=postgresql://user:pass@localhost/agora_ai
# - REDIS_URL=redis://localhost:6379
# - GROQ_API_KEY=<your-groq-key>
# - COHERE_API_KEY=<your-cohere-key>
# - ELEVENLABS_API_KEY=<your-elevenlabs-key>
```

#### 3. Database Setup
```bash
# Run migrations
alembic upgrade head

# Seed initial data (optional)
python -c "from src.models import setup_db; setup_db()"
```

#### 4. Start Services
```bash
# Using Docker Compose (recommended)
docker-compose up -d postgres redis

# Or run locally
# Terminal 1: Redis
redis-server

# Terminal 2: PostgreSQL (if not containerized)
# Terminal 3: Python worker
python main.py

# Terminal 4: API server (if separate)
uvicorn main:app --reload --port 8000
```

#### 5. Verify Setup
```bash
# Check Redis connection
redis-cli ping  # Should return PONG

# Check PostgreSQL
psql $DATABASE_URL -c "SELECT version();"

# Check API
curl http://localhost:8000/health
```

---

## 🔄 Core Workflows

### 1. Starting a Match
```
User initiates match (AP/BP, motion, side, role, skill_level)
        ↓
POST /api/matches → Create DebateSession + CasePrep
        ↓
Publish START_MATCH event to Redis
        ↓
Consumer receives → Determines first speaker
        ↓
If AI first → generate_ai_response() starts
If Human first → Frontend notified to activate mic
```

### 2. AI Turn Generation (4-Phase Pipeline)
```
generate_ai_response(match_id, turn_index)
        ↓
Phase 1: Parse clash matrix from transcript
        ↓
Phase 2: Generate queries (throttled by difficulty)
        ↓
Phase 3: Search & rank evidence from case prep embeddings
        ↓
Phase 4: Stream generation + persist Turn record
        ↓
Publish TURN_STARTED event (speaker: "ai", role, turn_index)
        ↓
Frontend receives → Start ElevenLabs TTS → Play audio
        ↓
Audio finishes → Frontend captures timing (start, end, duration)
        ↓
Frontend publishes TURN_CHANGED with timing data
```

### 3. Turn Persistence
```
Consumer receives TURN_CHANGED
        ↓
Extract: ai_speech_duration_ms, ai_speech_start_time_utc, ai_speech_end_time_utc
        ↓
Call update_turn_timing()
        ↓
Database: Turn record updated with (started_at, ended_at, duration_seconds)
```

### 4. Match Completion & Adjudication
```
Consumer detects current_turn_index >= len(schedule)
        ↓
Mark match status = "finished"
        ↓
Publish MATCH_COMPLETE event
        ↓
Spawn run_adjudication_worker() async task
        ↓
Worker evaluates each speaker (argumentation quality, persuasiveness)
        ↓
Persist SpeakerScore records
        ↓
Publish ADJUDICATION_COMPLETE with results
```

---

## 🗣️ Debate Formats

### Asian Parliamentary (AP)
- **Structure**: 6 speakers (3 gov, 3 opp), alternating speeches
- **Speech Duration**: ~7 minutes each
- **Roles**:
  - Government: Prime Minister (PM), Deputy PM (DPM), Member of Government (MG)
  - Opposition: Leader of Opposition (LO), Deputy LO (DLO), Member of Opposition (MO)
- **Implementation**: [src/ai/prompts/debater_prompts.py](src/ai/prompts/debater_prompts.py#L1-L50)

### British Parliamentary (BP)
- **Structure**: 8 speakers (4 teams), 2 speakers per team
- **Speech Duration**: ~8 minutes each
- **Teams**:
  - Opening Government, Opening Opposition
  - Closing Government, Closing Opposition
- **Roles**: Prime Minister, Deputy PM, Member, Whip (per team)
- **Implementation**: [src/ai/prompts/debater_prompts.py](src/ai/prompts/debater_prompts.py#L100-L150)

---

## 📊 Difficulty System

### Architecture
Configuration-driven difficulty control with **3 independent levers**:

```python
# From src/core/difficulty.py
DIFFICULTY_MATRIX = {
    "beginner": {
        "info_throttle": {"max_search_queries": 1, "rag_top_k": 1},
        "memory_drop": {"argument_drop_probability": 0.5},
        "persona": {"temperature": 0.8, "persona_modifier": "..."}
    },
    "intermediate": {...},
    "advanced": {...}
}
```

### Implementation in Debater Agent
- **Phase 2**: Query count limiting
- **Phase 3**: Top-k filtering (evidence count)
- **Phase 4**: Temperature + persona injection

### Database
- User.skill_level: Enum(BEGINNER, INTERMEDIATE, ADVANCED)
- DebateSession.skill_level: Inherited from user at match creation

---

## 📡 API Reference

### Match Endpoints

#### Create Match
```http
POST /api/matches
Content-Type: application/json

{
  "motion": "This house believes AI should regulate itself",
  "format": "ap",  # or "bp"
  "side": "government",
  "role": "prime_minister",
  "skill_level": "intermediate"
}

Response: 201 Created
{
  "id": "uuid",
  "status": "started",
  "format": "ap",
  "user_role": "prime_minister",
  "created_at": "2025-04-30T10:30:00Z"
}
```

#### Get Match
```http
GET /api/matches/{match_id}

Response: 200 OK
{
  "id": "uuid",
  "status": "finished",
  "format": "ap",
  "turns": [
    {
      "turn_index": 0,
      "speaker_role": "prime_minister",
      "speaker_type": "ai",
      "transcript": "Thank you, Mr. Speaker...",
      "started_at": "2025-04-30T10:30:00Z",
      "ended_at": "2025-04-30T10:37:00Z",
      "duration_seconds": 420
    }
  ]
}
```

### Redis Event Schema

#### START_MATCH
```json
{
  "action": "START_MATCH",
  "match_id": "uuid"
}
```

#### TURN_CHANGED
```json
{
  "action": "TURN_CHANGED",
  "match_id": "uuid",
  "ai_speech_start_time_utc": "2025-04-30T10:30:00Z",
  "ai_speech_end_time_utc": "2025-04-30T10:37:00Z",
  "ai_speech_duration_ms": 420000
}
```

---

## 🛠️ Development

### Running Tests
```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires DB)
pytest tests/integration -v

# With coverage
pytest --cov=src tests/
```

### Code Quality
```bash
# Linting
pylint src/

# Type checking
mypy src/

# Formatting
black src/

# All checks
make lint  # If Makefile exists
```

### Adding New Features

#### 1. New Debate Format
- Create `src/ai/prompts/[format]_prompts.py`
- Update `DebaterAgent.normalize_role()` with mapping
- Add constraints to `src/engine/rules.py`
- Create repository: `src/repositories/[format]/matches.py`

#### 2. New LLM Service
- Create client in `src/ai/clients/[service]_client.py`
- Implement interface: `invoke(prompt, **kwargs) → str`
- Register in `src/services/llm_service.py`
- Add to `config.py` for routing

#### 3. New Event Type
- Define event structure in consumer
- Add handler in `start_redis_consumer()`
- Publish via `client.publish(channel, json.dumps(event))`

---

## 🚢 Deployment

### Docker Build
```bash
docker build -t agora-ai-engine:latest .

docker run -d \
  --env-file .env \
  --network agora-net \
  agora-ai-engine:latest
```

### Kubernetes Deployment
```bash
# Apply ConfigMap + Secrets
kubectl apply -f k8s/

# Deploy
kubectl apply -f k8s/deployment.yaml

# Check status
kubectl get pods -l app=agora-ai-engine
```

### Environment Variables (Production)
```
DATABASE_URL=postgresql://prod-user:secure-pass@prod-db/agora_prod
REDIS_URL=redis://prod-redis:6379
GROQ_API_KEY=gsk_xxx
COHERE_API_KEY=cohere_xxx
ELEVENLABS_API_KEY=xxx
LOG_LEVEL=info
SENTRY_DSN=https://xxx@sentry.io/xxx
```

---

## 🤝 Contributing

### Branch Strategy
- `main`: Production-ready code
- `develop`: Integration branch
- `feature/[feature-name]`: New features
- `bugfix/[issue-id]`: Bug fixes

### Commit Convention
```
feat: Add new difficulty lever
fix: Resolve query count limiting bug
docs: Update README
refactor: Simplify debate orchestrator
test: Add test coverage for adjudicator
```

### PR Requirements
1. ✅ Tests pass (`pytest`)
2. ✅ Type hints present (`mypy`)
3. ✅ Code formatted (`black`)
4. ✅ Docstrings added
5. ✅ Changelog updated

---

## 🔍 Troubleshooting

### Common Issues

#### Redis Connection Error
```
Error: ConnectionRefusedError: [Errno 111] Connection refused
```
**Solution:**
```bash
# Check Redis is running
redis-cli ping

# Or start with Docker
docker-compose up -d redis
```

#### Database Migration Failed
```
Error: FAILED NEW instance() due to IntegrityError
```
**Solution:**
```bash
# Check current revision
alembic current

# Downgrade and re-run
alembic downgrade -1
alembic upgrade head
```

#### LLM Rate Limiting
```
Error: groq.RateLimitError: 429 Too Many Requests
```
**Solution:**
- Implement exponential backoff in `groq_client.py`
- Check Groq API quota
- Use fallback to OpenAI via `llm_service.py`

#### Timing Data Missing
```
Turn.duration_seconds = 0, Turn.ended_at = NULL
```
**Solution:**
- Verify frontend sends timing in TURN_CHANGED event
- Check Redis event payload: `redis-cli SUBSCRIBE "debate:*"`
- Verify `update_turn_timing()` is called in consumer

---

## 📊 Metrics & Monitoring

### Key Metrics to Track
- **Debate Duration**: Total match time (started_at → completion)
- **Turn Duration**: Per-speaker speech time (frontend-measured)
- **LLM Latency**: Generation time per phase
- **Vector Search Latency**: Embedding retrieval time
- **Adjudication Time**: Grading async task duration

### Logging
```python
logger.info(
    f"[CONSUMER] Match {match_id} completed in {duration:.2f}s",
    extra={
        "match_id": match_id,
        "format": format_type,
        "speakers": len(schedule),
        "duration_seconds": duration
    }
)
```

---

## 📚 Additional Resources

- [Debate Formats Guide](docs/DEBATE_FORMATS.md)
- [LLM Integration Guide](docs/LLM_INTEGRATION.md)
- [Architecture Decision Records](docs/ADRs/)
- [Performance Tuning](docs/PERFORMANCE.md)
- [API Documentation](docs/API.md)

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details

---

## 👥 Maintainers

- **Core Team**: [Your Team]
- **Technical Lead**: [Name]

For questions or issues, please open a GitHub issue or reach out to the team.

---

## 🎓 Citation

If you use Agora AI Engine in research or production, please cite:

```bibtex
@software{agora_ai_engine_2025,
  title={Agora AI Engine: Real-time Competitive Debate Orchestration},
  author={[Author Names]},
  year={2025},
  url={https://github.com/im-rk/agora-ai-engine}
}
```

---

**Last Updated**: April 30, 2025  
**Status**: Production Ready ✅
