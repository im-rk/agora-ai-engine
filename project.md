# Agora AI Debate Engine — Project Documentation

## Overview

Agora is an AI-powered debate engine backend built with FastAPI, PostgreSQL, and LLMs. It enables structured debate preparation and (upcoming) real-time AI vs. human debate matches.

**Core capabilities:**
- Create and manage debate matches
- Generate structured AI case preparation (arguments, counter-arguments, evidence)
- Engage in AI vs. Human debates *(Phase 2 — in progress)*

---

## Architecture

The project follows Clean Architecture with DDD-inspired layering:

```
API Layer (FastAPI)
    ↓
Service Layer (Business Logic)
    ↓
Repository Layer (DB Interactions)
    ↓
Database (PostgreSQL)
    ↓
AI Agents (LangChain / LLM)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| AI Orchestration | LangChain |
| LLM Providers | OpenAI / Groq |
| Embeddings | Cohere |
| Testing | Pytest |

---

## Folder Structure

```
├── 📁 alembic
│   ├── 📁 versions
│   │   ├── 🐍 0966735ff365_initial_schema_with_pgvector_and_ai_logs.py
│   │   ├── 🐍 44fb976e778d_init_complete_schema.py
│   │   └── 🐍 ebcc6cfe159b_init_complete_schema.py
│   ├── 📄 README
│   ├── 🐍 env.py
│   └── 📄 script.py.mako
├── 📁 src
│   ├── 📁 ai
│   │   ├── 📁 agents
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 adjudicator.py
│   │   │   ├── 🐍 debater.py
│   │   │   ├── 🐍 prep_coach.py
│   │   │   └── 🐍 sniper.py
│   │   ├── 📁 clients
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 cohere_client.py
│   │   │   ├── 🐍 groq_client.py
│   │   │   └── 🐍 openai_client.py
│   │   ├── 📁 prompts
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 adjudicator_prompts.py
│   │   │   ├── 🐍 debater_prompts.py
│   │   │   ├── 🐍 prep_coach_prompts.py
│   │   │   └── 🐍 sniper_prompts.py
│   │   └── 🐍 __init__.py
│   ├── 📁 api
│   │   ├── 📁 rest
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 history.py
│   │   │   ├── 🐍 matches.py
│   │   │   └── 🐍 users.py
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 dependencies.py
│   ├── 📁 core
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 config.py
│   │   ├── 🐍 database.py
│   │   ├── 🐍 redis_client.py
│   │   └── 🐍 security.py
│   ├── 📁 engine
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 rules.py
│   │   └── 🐍 state.py
│   ├── 📁 exceptions
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 custom_errors.py
│   │   └── 🐍 handlers.py
│   ├── 📁 models
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 debate.py
│   │   ├── 🐍 results.py
│   │   ├── 🐍 setup.py
│   │   └── 🐍 user.py
│   ├── 📁 repositories
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 case_prep_repo.py
│   │   ├── 🐍 debate_repo.py
│   │   ├── 🐍 results_repo.py
│   │   └── 🐍 user_repo.py
│   ├── 📁 schemas
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 debate_schema.py
│   │   ├── 🐍 prep_coach_schema.py
│   │   ├── 🐍 results_schema.py
│   │   └── 🐍 user_schema.py
│   ├── 📁 services
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 case_prep_service.py
│   │   ├── 🐍 embedding_service.py
│   │   ├── 🐍 grading_service.py
│   │   ├── 🐍 llm_service.py
│   │   ├── 🐍 match_service.py
│   │   └── 🐍 user_service.py
│   ├── 📁 workers
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 redis_consumer.py
│   └── 🐍 __init__.py
├── 📁 tests
│   ├── 📁 integration
│   │   ├── 📁 api
│   │   │   ├── 📁 rest
│   │   │   │   ├── 🐍 __init__.py
│   │   │   │   └── 🐍 test_matches_api.py
│   │   │   └── 🐍 __init__.py
│   │   ├── 📁 repositories
│   │   │   ├── 🐍 __init__.py
│   │   │   └── 🐍 test_debate_repo.py
│   │   └── 🐍 __init__.py
│   ├── 📁 unit
│   │   ├── 📁 ai
│   │   │   ├── 📁 agents
│   │   │   │   ├── 🐍 __init__.py
│   │   │   │   └── 🐍 test_prep_coach.py
│   │   │   └── 🐍 __init__.py
│   │   ├── 📁 schemas
│   │   │   ├── 🐍 __init__.py
│   │   │   └── 🐍 test_debate_schema.py
│   │   ├── 📁 services
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 test_case_prep_service.py
│   │   │   └── 🐍 test_match_service.py
│   │   └── 🐍 __init__.py
│   ├── 🐍 __init__.py
│   └── 🐍 conftest.py
├── ⚙️ .env.example
├── ⚙️ .gitignore
├── ⚙️ alembic.ini
├── 🐍 main.py
├── 📝 project.md
├── ⚙️ pyproject.toml
├── 📝 readme.md
├── 📄 requirements.txt
├── 📝 test_readme.md
├── 🐍 test_redis.py
└── 📄 uv.lock
```



---

## Core Entities

| Entity | Description |
|---|---|
| `User` | Debate participant |
| `Motion` | The debate topic/proposition |
| `DebateSession` | A single debate instance |
| `CasePrep` | AI-generated case preparation container |
| `ArgumentEmbedding` | Vector embeddings for semantic search |
| `AICallLog` | Audit log for all LLM API calls |

---

# Phase 1 — Completed

## Match Creation Flow

1. Create a `Motion` (custom topic)
2. Create a `DebateSession` linked to the motion
3. Create a `CasePrep` container for AI output

## Prep Coach AI Agent

Uses LangChain with structured output to generate a complete case prep package:

- **Model Definition** — frames the key terms of the debate
- **Arguments** — supporting points for the assigned side
- **Counter-Arguments** — anticipated opposition points
- **Evidence** — supporting facts and examples

## Case Prep Pipeline

```
match_service
    ↓
case_prep_service
    ↓
prep_coach (AI Agent)
    ↓
DB Storage (CasePrep, ArgumentEmbedding, AICallLog)
```

## Embeddings

- Generated via Cohere
- Stored in `ArgumentEmbedding`
- Designed for semantic search in future phases

## AI Call Logging

All LLM interactions are logged to `AICallLog`, capturing:
- The prompt sent
- The model used
- The raw output received

## Testing

Pytest-based unit test suite with mocked AI (no real API calls made during tests).

**Coverage:**
- `prep_coach` — AI agent unit tests
- `case_prep_service` — service layer tests
- `match_service` — orchestration tests

## Key Learnings

- FK constraints must be respected in test fixtures
- Async functions require `pytest-asyncio`
- Never call real LLMs in tests — use mocking
- The service layer should own all orchestration logic

---

## Current End-to-End Flow

```
POST /matches
    ↓
matches.py          (API layer)
    ↓
match_service.py    (Service layer)
    ↓
case_prep_service.py
    ↓
prep_coach.py       (AI Agent)
    ↓
LLM API
    ↓
DB  →  CasePrep + ArgumentEmbedding + AICallLog
```

---

# Phase 2 — Debate Engine (In Progress)

## Goal

Build a real-time, turn-based debate system where users can go head-to-head against an AI opponent.

## Features to Build

**Speech System**
- User submits a speech via API
- AI generates a structured counter-speech in response

**Turn Engine**
- Manages debate rounds (e.g. Opening → Rebuttal → Summary)
- Tracks the active speaker and round state

**Debate Agent**
- New AI agent responsible for generating opponent speeches
- Draws on case prep context for coherent argumentation

**Storage**
- All speeches persisted to DB per debate session

## Planned Flow

```
POST /matches
POST /matches/{id}/speak
```

## Upcoming Components

| Component | Type |
|---|---|
| `debate_service.py` | Service layer |
| `Speech` | SQLAlchemy model |
| `SpeechRepository` | Repository layer |
| `debate_agent.py` | AI agent |
| `/speak` endpoint | API route |

---

# Engineering Principles

| Principle | Application |
|---|---|
| Separation of Concerns | API, service, repository, and AI layers are fully decoupled |
| Clean Architecture | Dependencies flow inward; AI is a detail, not the core |
| Testability | All AI calls are mockable; no external dependencies in unit tests |
| Observability | Every LLM interaction is logged with prompt, model, and output |
| Scalability | Modular, feature-based folder structure supports parallel development |

---

## Notes

This project is being built incrementally with an emphasis on:

- Real-world backend architecture patterns
- AI system design and LLM integration
- Production-level practices (logging, testing, clean separation of concerns)