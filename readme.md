<div align="center">

<img src="assets/Adjucation1.png" alt="Agora — Adjudication powered by the Agora AI Engine" width="100%" />

<br/>

# Agora — AI Engine

A FastAPI service that orchestrates competitive parliamentary debates. It runs a four-phase retrieval-augmented debater, a five-phase WUDC-style adjudicator, and persists every artifact of every match. Async-first, format-aware, difficulty-throttled, and streaming-native.

<br/>

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/Postgres-14-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-1024D-8B5CF6?style=for-the-badge)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Groq](https://img.shields.io/badge/Groq-LLaMA--3.1-F55036?style=for-the-badge)](https://groq.com/)
[![LangChain](https://img.shields.io/badge/LangChain-1.2-22C55E?style=for-the-badge)](https://www.langchain.com/)
[![Status](https://img.shields.io/badge/status-production-22C55E?style=for-the-badge)]()

<br/>

<a href="https://skillicons.dev">
  <img src="https://skillicons.dev/icons?i=python,fastapi,postgres,redis,supabase&theme=dark" />
</a>

<br/>
<br/>

[Architecture](#architecture) · [4-Phase Debater](#the-four-phase-ai-debate-pipeline) · [5-Phase Adjudicator](#the-five-phase-wudc-adjudication-pipeline) · [Engineering Decisions](#engineering-decisions) · [Getting Started](#getting-started)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Service Responsibilities](#service-responsibilities)
3. [Visual Context](#visual-context)
4. [Architecture](#architecture)
5. [The Four-Phase AI Debate Pipeline](#the-four-phase-ai-debate-pipeline)
6. [The Five-Phase WUDC Adjudication Pipeline](#the-five-phase-wudc-adjudication-pipeline)
7. [Difficulty System](#difficulty-system)
8. [Debate Formats](#debate-formats)
9. [Engineering Decisions](#engineering-decisions)
10. [Project Structure](#project-structure)
11. [Database Schema](#database-schema)
12. [RAG and Vector Search](#rag-and-vector-search)
13. [Redis Event Contract](#redis-event-contract)
14. [REST API](#rest-api)
15. [Tech Stack](#tech-stack)
16. [Getting Started](#getting-started)
17. [Environment Variables](#environment-variables)
18. [Development](#development)
19. [Deployment](#deployment)
20. [Observability](#observability)
21. [Troubleshooting](#troubleshooting)
22. [Roadmap](#roadmap)

---

## Overview

The AI engine is the intelligence layer of the Agora competitive debate platform. It owns the rules, the schedule, the prompts, the retrieval, the streaming, and the final adjudication — every cognitive step that turns a motion and a microphone into a graded competitive debate.

The service is headless. It never serves WebSockets, never plays audio, and has no view of the user interface. It listens to Redis events, runs LLM pipelines, persists to Postgres, and republishes streamed tokens for the gateway to deliver.

### Where this service sits

Agora is composed of three services. This repository is the intelligence layer.

| Service | Responsibility | Stack |
|---|---|---|
| **agora-frontend** | Browser UI, WebSocket lifecycle, microphone capture, audio playback queue | Next.js, React, TypeScript, Zustand |
| **agora-gateway** | WebSocket broker, STT/TTS multiplexer, reverse proxy, Redis state mutator | Go, Gorilla, Redis |
| **agora-ai-engine** *(this repo)* | Four-phase debater, five-phase adjudicator, RAG, persistence | Python, FastAPI, LangChain, pgvector |

---

## Service Responsibilities

**Match lifecycle orchestration.** Listens for `START_MATCH` and `TURN_CHANGED` events, advances the speaker schedule, and either spawns AI generation or notifies the frontend that the human's turn has begun.

**Four-phase AI speech generation.** For each AI turn, parses the clash matrix from the transcript, synthesizes search queries, retrieves and re-ranks evidence from a match-scoped vector store, and streams a final speech word-by-word through Redis callbacks.

**Five-phase WUDC adjudication.** On match completion, extracts macro-clashes, builds a weighted clash matrix, grades the debate on the four WUDC pillars, scores each speaker individually with verbatim quotes, and writes a chief-adjudicator-style summary.

**Case-prep generation.** Before a match begins, generates a structured argument brief for the human side (claims, counter-arguments, evidence). Embeds every argument with Cohere and indexes it in pgvector under the match's namespace.

**Persistence.** Writes every artifact to Postgres: motions, case preps, sessions, turns, POIs, adjudication results, per-user performance, and a full LLM call audit log.

**REST surface.** Exposes match CRUD, case-prep retrieval, adjudication retrieval, and a polling endpoint for adjudication status. The Go gateway reverse-proxies the frontend to these routes.

---

## Visual Context

The AI engine has no UI of its own. Every artifact in the screenshots below — case preps, streamed speeches, adjudications, score breakdowns — is generated by this service.

<table>
  <tr>
    <td width="50%" align="center"><strong>Setup — Side Assignment</strong><br/><img src="assets/SetupDebate1.png" alt="Setup" /></td>
    <td width="50%" align="center"><strong>Case Prep — generated by prep_coach</strong><br/><img src="assets/CasePrep1.png" alt="Case Prep" /></td>
  </tr>
  <tr>
    <td width="50%" align="center"><strong>Live Streaming Token Output</strong><br/><img src="assets/DebateArena2.png" alt="AI Speaking" /></td>
    <td width="50%" align="center"><strong>Five-Phase Adjudication</strong><br/><img src="assets/Adjucation1.png" alt="Adjudication" /></td>
  </tr>
  <tr>
    <td width="50%" align="center"><strong>Verdict and Score Banner</strong><br/><img src="assets/Results1.png" alt="Verdict" /></td>
    <td width="50%" align="center"><strong>WCM and WUDC Pillar Breakdown</strong><br/><img src="assets/Results2.png" alt="WCM Pillars" /></td>
  </tr>
  <tr>
    <td colspan="2" align="center"><strong>Speaker-level grading with verbatim quotes and coach feedback</strong><br/><img src="assets/Results3.png" alt="Speaker Scores" width="100%" /></td>
  </tr>
</table>

---

## Architecture

### Topology

```mermaid
graph TD
    subgraph Edge["Edge"]
        FE[Next.js Frontend]
        GW[Go Gateway · :8080]
        FE <-->|WSS| GW
    end

    subgraph Engine["Python AI Engine · :8000 (this repository)"]
        FAPI[FastAPI · main.py]
        CONS[workers/redis_consumer.py<br/>Pub/sub event loop]
        AIRG[workers/ai_response_generator.py]
        ADJW[workers/adjudication_worker.py]
        DEB[ai/agents/debater.py<br/>4-phase pipeline]
        ADJ[ai/agents/adjudicator.py<br/>5-phase pipeline]
        PREP[ai/agents/prep_coach.py]
        RAG[ai/tools/rag_engine.py]
        STATE[engine/state.py<br/>MatchStateManager]

        FAPI --> CONS
        CONS --> AIRG
        CONS --> ADJW
        AIRG --> DEB
        ADJW --> ADJ
        DEB --> RAG
        DEB --> STATE
        ADJ --> STATE
    end

    subgraph DataPlane["Data plane"]
        REDIS[(Redis<br/>pub/sub + LiveMatchState)]
        DB[(PostgreSQL<br/>+ pgvector 1024D)]
    end

    subgraph LLMs["LLM services"]
        GROQ[Groq · llama-3.1-8b-instant]
        OAI[OpenAI · gpt-4o-mini fallback]
        COH[Cohere · embed-english-v3.0]
        SB[(Supabase Auth)]
        LF[Langfuse · observability]
    end

    GW <-->|pub/sub| REDIS
    CONS <-->|pub/sub| REDIS
    STATE <-->|GET / SET| REDIS
    AIRG --> DB
    ADJW --> DB
    RAG -->|cosine search| DB
    DEB --> GROQ
    PREP --> OAI
    RAG --> COH
    ADJ --> GROQ
    FAPI --> SB
    DEB -.->|trace| LF
    ADJ -.->|trace| LF
```

### Two surfaces in one process

The engine runs two concurrent surfaces inside one process, both managed by FastAPI's `lifespan`:

1. **REST API** — synchronous endpoints for match creation, case prep, history, and adjudication retrieval. Mounted on `:8000`.
2. **Redis consumer** — an async background task spawned from FastAPI's `lifespan`, listening on `psubscribe("debate:*")`. This is where real-time orchestration happens.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_task = asyncio.create_task(start_redis_consumer())
    yield
    consumer_task.cancel()
```

---

## The Four-Phase AI Debate Pipeline

Located in [`src/ai/agents/debater.py`](src/ai/agents/debater.py). Every AI speech runs the four phases below — format-aware (AP versus BP) and difficulty-throttled (Beginner, Intermediate, Advanced).

```mermaid
graph LR
    Trigger[TURN_CHANGED · AI is next] --> P1
    P1[Phase 1<br/>State Tracker<br/>Parse Clash Matrix] --> P2
    P2[Phase 2<br/>Sniper<br/>Synthesize Search Queries] --> P3
    P3[Phase 3<br/>Researcher<br/>Retrieve and Re-rank] --> P4
    P4[Phase 4<br/>Debater<br/>Stream Spoken Speech] --> Out[AI_TOKEN events<br/>Redis → Frontend]
```

### Phase 1 — State Tracker

**Function.** `phase1_parse_clash_matrix()`
**Model.** `llama-3.1-8b-instant`, `temperature=0.1`, JSON mode.

Parses the transcript so far into a structured clash matrix:

```json
{
  "opponent_claims": [...],
  "our_dropped_args": [...],
  "vulnerabilities": [...]
}
```

### Phase 2 — Query Synthesis

**Function.** `phase2_generate_search_queries()`
**Model.** `llama-3.1-8b-instant`, `temperature=0.3`.

Turns the clash matrix into role-specific search queries. A Whip generates queries about clash weighting; a Prime Minister generates queries about framing; a Member generates queries about new analytical angles.

Throttled by difficulty: Beginner generates 1 query, Intermediate 2, Advanced 4.

### Phase 3 — Retrieval and Re-ranking

**Function.** `phase3_retrieve_and_rerank()`
**Engine.** [`src/ai/tools/rag_engine.py`](src/ai/tools/rag_engine.py).

For each query, performs an async semantic search over `argument_embeddings` filtered by `match_id` and `side` (and optionally `role`). Uses pgvector cosine similarity.

Throttled by difficulty: Beginner retrieves top 1, Intermediate top 3, Advanced top 5.

Memory drop: Beginner forgets 50% of opponent claims, Intermediate 10%, Advanced 0%.

### Phase 4 — Streaming Generation

**Function.** `phase4_generate_response_streaming()`
**Model.** `llama-3.1-8b-instant`, `streaming=True`, `temperature ∈ {0.1, 0.4, 0.8}`.

Composes the final speech with:

- The clash matrix from Phase 1.
- The retrieved evidence from Phase 3.
- A forced stance instruction (Government affirms, Opposition negates).
- A persona modifier ("You are a novice debater..." vs "You are a WUDC champion...").
- Format-specific role constraints (PM frames, Whip weighs, Member introduces).

Tokens stream through `RedisStreamingCallbackHandler`, are published per token to Redis, are forwarded by the Go gateway, and are typed onto the frontend in real time.

```python
class RedisStreamingCallbackHandler(AsyncCallbackHandler):
    async def on_llm_new_token(self, token: str, **kwargs):
        await self.redis.publish(
            f"debate:{self.match_id}:turns",
            json.dumps({"event": "AI_TOKEN", "text": token})
        )
```

### Post-processing

- The full text is persisted to the `turns` table.
- An `AICallLog` row records every phase's prompt, model, temperature, and raw output (audit trail).
- `AI_THOUGHT_COMPLETE` is published to signal the gateway to flush any remaining TTS audio.

---

## The Five-Phase WUDC Adjudication Pipeline

Located in [`src/ai/agents/adjudicator.py`](src/ai/agents/adjudicator.py). Triggered by `MATCH_COMPLETE`. Mirrors the methodology used by chief adjudicators at the World Universities Debating Championship.

```mermaid
graph TD
    Trigger[MATCH_COMPLETE] --> P1
    P1[Phase 1<br/>Extract Macro Clashes<br/>3-5 themes] --> P2
    P2[Phase 2<br/>Build Weighted Clash Matrix<br/>Weight × Delta] --> P3
    P3[Phase 3<br/>WUDC Pillar Analysis<br/>Matter · Manner · Method · Role] --> P4
    P4[Phase 4<br/>Grade Each Speaker<br/>5 sub-scores · /100] --> P5
    P5[Phase 5<br/>Final Summary<br/>+ 3 Key Decisions] --> Save[(adjudication_results)]
    Save --> Pub[ADJUDICATION_COMPLETE event]
```

### Phase 1 — Macro-Clash Extraction

Identifies three to five high-level themes that structured the debate (for example, "The Economic Impact Clash", "The Logistical Feasibility Clash", "The Fairness and Equity Clash"). Themes, not individual arguments.

### Phase 2 — Weighted Clash Matrix (WCM)

For each clash, the LLM assigns:

- **Weight** ∈ [1, 5] — importance to the debate's outcome.
- **Delta** ∈ [-2, +2] — winner of the clash (negative indicates Opposition won, positive indicates Government won).
- **Weighted Score** = Weight × Delta.

The Net Logic Score is `sum(weighted_scores)`. This is the mathematical backbone of the verdict.

**Hallucination guard.** `_recalculate_totals()` re-derives net score from components in Python. The LLM's arithmetic is never trusted.

### Phase 3 — WUDC Pillar Breakdown

Grades each team out of 100, split into four pillars of 25 points each:

| Pillar | Measures |
|---|---|
| Matter | Logic, evidence, analytical depth (anchored to WCM math) |
| Manner | Persuasiveness, delivery, rhetoric |
| Method | Case structure, organization, signposting |
| Role | Fulfillment of speaker-specific WUDC duties |

### Phase 4 — Per-Speaker Grading

Every speaker receives five sub-scores (each /10), totaled and multiplied by 2:

| Sub-score | What it measures |
|---|---|
| Argument | Strength of original analysis |
| Evidence | Use of warrants and examples |
| Responsiveness | Rebuttal quality |
| Structure | Internal organization of the speech |
| Persona | Stage presence, confidence |

Each grade includes a mandatory verbatim quote pulled from the speaker's transcript. The Prime Minister's responsiveness receives a baseline 8-10 because the PM cannot rebut what has not yet been said.

### Phase 5 — Final Summary

A 150-200 word chief-adjudicator-style statement followed by three itemized key decisions. The winning team is determined strictly by the higher average speaker score — no subjective tie-breakers.

### Persistence

The full structured result is written to `adjudication_results` (single JSONB row per match), and `ADJUDICATION_COMPLETE` is published on Redis for the frontend's auto-redirect.

---

## Difficulty System

Three independent levers, defined as a single Pydantic config in [`src/core/difficulty.py`](src/core/difficulty.py).

| Lever | Beginner | Intermediate | Advanced |
|---|---|---|---|
| Info throttle (queries × top-k) | 1 query, top 1 | 2 queries, top 3 | 4 queries, top 5 |
| Memory drop (forgets opponent claims) | 50% | 10% | 0% |
| Persona modifier (LLM temperature and style) | `temp=0.8`, novice | `temp=0.4`, solid | `temp=0.1`, WUDC champion |

Applied uniformly:

- **Phase 2** uses `config.max_search_queries` to bound query count.
- **Phase 3** uses `config.rag_top_k` to bound evidence.
- **Phase 3** uses `config.argument_drop_probability` for memory drop.
- **Phase 4** injects `config.temperature` and `config.persona_modifier` into the system prompt.

---

## Debate Formats

### Asian Parliamentary (AP) — 6 speakers

```
1. Prime Minister              (Government)
2. Leader of Opposition        (Opposition)
3. Deputy Prime Minister       (Government)
4. Deputy Leader of Opposition (Opposition)
5. Government Whip             (Government)
6. Opposition Whip             (Opposition)
```

Approximately seven-minute speeches. Prompts in [`src/ai/prompts/ap/`](src/ai/prompts/ap).

### British Parliamentary (BP) — 8 speakers, 4 teams

```
Opening Government:    1. PM     · 3. Deputy PM
Opening Opposition:    2. LO     · 4. Deputy LO
Closing Government:    5. Member · 7. Whip
Closing Opposition:    6. Member · 8. Whip
```

Approximately eight-minute speeches. Prompts in [`src/ai/prompts/bp/`](src/ai/prompts/bp).

Schedules are built by `engine/state.MatchStateManager._generate_schedule()`. The frontend's role enum, the gateway's voice mapping, and this engine's role normalizers all line up via shared schemas.

---

## Engineering Decisions

The following are the non-trivial technical decisions made while building the engine. Each is framed as a problem and the constraint that drove the solution.

### 1. Refuse to trust LLM arithmetic

**Problem.** Competitive debate adjudication depends on a deterministic score. LLMs are notoriously unreliable at arithmetic — a model might output "Total: 92" when the underlying component scores sum to 87. Trusting the LLM's total means publishing wrong verdicts.

**Solution.** Every numeric field returned by the LLM is treated as a hint. Python re-derives every total from components in `_recalculate_totals()`:

- Net Logic Score is the sum of `weight × delta` across all clashes.
- Speaker totals are the sum of the five sub-scores multiplied by 2.
- Team totals are the sum of the four pillar scores.

If the LLM's output and the recalculated value disagree, the recalculated value is persisted and the divergence is logged.

### 2. Schedule-driven, not LLM-driven orchestration

**Problem.** Asking an LLM "whose turn is it?" leaks state into prompt engineering. An LLM that hallucinates the schedule produces broken debates.

**Solution.** Match state — schedule, current turn index, speaker roles — is a `LiveMatchState` Pydantic model serialized as JSON in Redis. The consumer reads this state to decide what happens next. The LLM is a worker that generates a single speech when told to. It never controls the flow.

### 3. Difficulty as a single source of truth

**Problem.** "Difficulty" is a fuzzy concept. A naive implementation would scatter difficulty conditionals through Phase 2, Phase 3, and Phase 4 of the debater. Changes would require touching multiple files and risking inconsistency.

**Solution.** One `DebateDifficultyConfig` Pydantic object encapsulates all three levers (queries, top-k, memory drop, temperature, persona text). `get_difficulty_config(level)` returns the config. Phases read the relevant fields. Adding a fourth lever — say, time-pressure simulation — requires editing one file.

### 4. Match-scoped RAG isolation

**Problem.** The same motion can be debated by many users. Embedding all arguments into a single shared vector index would leak strategy across matches and across users on opposing sides.

**Solution.** Every embedding row carries `match_id`, `user_id`, `side`, and `role`. Retrieval queries always filter on `match_id` and `side`. There is no global retrieval surface — the AI can never see opponent arguments or arguments from other matches.

```python
results = await session.execute(
    select(ArgumentEmbedding)
    .where(ArgumentEmbedding.match_id == match_id)
    .where(ArgumentEmbedding.side == side)
    .order_by(ArgumentEmbedding.embedding.cosine_distance(query_vec))
    .limit(top_k)
)
```

### 5. Streaming through Redis instead of HTTP

**Problem.** The frontend needs token-by-token streaming, but the engine must remain isolated from WebSockets. Streaming over HTTP would couple the engine's lifetime to the connection lifetime.

**Solution.** `RedisStreamingCallbackHandler` is a LangChain `AsyncCallbackHandler` whose `on_llm_new_token` simply publishes to Redis. The engine has no idea who is consuming. The gateway subscribes and fans out. If the gateway dies, the engine continues; if the engine dies, the gateway delivers what it has and the frontend reconnects to the same Redis channel.

### 6. Per-match task tracking against duplicate generation

**Problem.** A reconnect storm or a duplicate `START_MATCH` event can cause two parallel AI generations for the same turn — two voices speaking over each other, two database rows for one turn.

**Solution.** The consumer holds an `active_tasks: dict[str, asyncio.Task]` map keyed by match ID. Before spawning a new AI task, it checks for an existing task; if one is running, it is cancelled and replaced (or, depending on context, skipped). Exactly one generation per (match, turn) is guaranteed.

### 7. Background worker inside FastAPI's lifespan

**Problem.** A separate worker process for the Redis consumer means two deployment artifacts, two health checks, two observability pipelines, two environments to keep in sync.

**Solution.** The consumer runs as an `asyncio.create_task` from FastAPI's `lifespan`. One process, one deployment unit, one health endpoint. The REST API and the consumer share the same database pool, the same logging configuration, and the same shutdown signal. Scaling horizontally requires one constraint: Redis pub/sub is broadcast, so only one instance can run until we migrate to Redis Streams with consumer groups.

---

## Project Structure

```
agora-ai-engine/
├── assets/                          README screenshots
├── alembic/
│   ├── versions/                    Alembic migrations
│   └── env.py
├── alembic.ini
│
├── src/
│   ├── ai/
│   │   ├── agents/
│   │   │   ├── debater.py           Four-phase pipeline
│   │   │   ├── adjudicator.py       Five-phase WUDC pipeline
│   │   │   ├── prep_coach.py        Case-prep generator
│   │   │   └── sniper.py            Cross-ex strategist
│   │   ├── clients/
│   │   │   ├── groq_client.py       Cached singleton ChatGroq
│   │   │   ├── openai_client.py     gpt-4o-mini fallback
│   │   │   └── cohere_client.py     Embeddings
│   │   ├── callbacks/
│   │   │   └── redis_stream.py      AsyncCallbackHandler to Redis
│   │   ├── prompts/
│   │   │   ├── adjudicator_prompts.py
│   │   │   ├── prep_coach_prompts.py
│   │   │   ├── ap/debater_prompts.py
│   │   │   └── bp/debater_prompts.py
│   │   └── tools/
│   │       └── rag_engine.py        pgvector semantic search
│   │
│   ├── api/
│   │   ├── routes/v1/
│   │   │   ├── auth.py              Supabase JWT verify
│   │   │   ├── motions.py
│   │   │   ├── users.py
│   │   │   ├── ap/                  AP match, case-prep, adjudication
│   │   │   └── bp/                  BP equivalents
│   │   └── dependencies.py          get_current_user, get_db
│   │
│   ├── core/
│   │   ├── config.py                Pydantic Settings
│   │   ├── database.py              SQLAlchemy engine + SessionLocal
│   │   ├── redis_client.py          Async Redis singleton
│   │   ├── difficulty.py            Three-lever matrix
│   │   ├── security.py              JWT verify
│   │   └── logging.py
│   │
│   ├── engine/
│   │   ├── state.py                 MatchStateManager (Redis schedule)
│   │   └── rules.py                 Format-specific constraints
│   │
│   ├── models/
│   │   ├── user.py                  User, SkillLevel
│   │   ├── debate.py                DebateSession, Turn, POI
│   │   ├── results.py               AdjudicationResult, UserPerformance
│   │   └── setup.py                 Motion, CasePrep, ArgumentEmbedding, AICallLog
│   │
│   ├── repositories/
│   │   ├── ap/matches.py            AP-specific persistence
│   │   ├── bp/matches.py            BP equivalents
│   │   └── adjudication_repo.py
│   │
│   ├── schemas/
│   │   ├── state_schema.py          LiveMatchState, Turn (Pydantic)
│   │   ├── adjudication.py          MacroClash, WCMEntry, PillarScore, SpeakerScore
│   │   └── ap|bp/matches.py         Request/response models
│   │
│   ├── services/
│   │   ├── ap/matches.py            AP business logic
│   │   ├── bp/matches.py            BP business logic
│   │   └── embedding_service.py     Cohere embed wrapper
│   │
│   └── workers/
│       ├── redis_consumer.py        psubscribe("debate:*") event loop
│       ├── ai_response_generator.py 4-phase orchestration + persistence
│       ├── transcript_handler.py    Transcript formatting helpers
│       └── adjudication_worker.py   5-phase orchestration + persistence
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── main.py                          FastAPI + lifespan(consumer)
├── pyproject.toml
├── requirements.txt
├── uv.lock
├── .env.example
└── readme.md                        This file
```

---

## Database Schema

PostgreSQL with the **pgvector** extension. Managed via Alembic.

```mermaid
erDiagram
    USERS ||--o{ DEBATE_SESSIONS : creates
    USERS ||--o{ CASE_PREPS : owns
    USERS ||--o{ USER_PERFORMANCE : earns
    MOTIONS ||--o{ DEBATE_SESSIONS : anchors
    MOTIONS ||--o{ CASE_PREPS : scoped-to
    CASE_PREPS ||--o{ ARGUMENT_EMBEDDINGS : vectorizes
    DEBATE_SESSIONS ||--|{ TURNS : contains
    DEBATE_SESSIONS ||--o{ POIS : interrupted-by
    DEBATE_SESSIONS ||--|| ADJUDICATION_RESULTS : produces
    DEBATE_SESSIONS ||--o{ AI_CALL_LOGS : traces
    DEBATE_SESSIONS ||--o{ USER_PERFORMANCE : scores

    USERS {
        uuid id PK
        text email
        text display_name
        enum skill_level
        timestamp created_at
    }
    MOTIONS {
        uuid id PK
        text motion_text
        enum category
        bool is_custom
    }
    CASE_PREPS {
        uuid id PK
        uuid user_id FK
        uuid motion_id FK
        enum side
        jsonb arguments
        jsonb counter_arguments
        jsonb evidence
    }
    ARGUMENT_EMBEDDINGS {
        uuid id PK
        uuid case_prep_id FK
        uuid match_id
        text content
        vector_1024 embedding
        text role
        text side
    }
    DEBATE_SESSIONS {
        uuid id PK
        uuid user_id FK
        uuid motion_id FK
        uuid case_prep_id FK
        enum format
        text human_role
        enum skill_level
        enum status
        bool poi_enabled
    }
    TURNS {
        uuid id PK
        uuid session_id FK
        int turn_number
        text speaker_role
        enum speaker_type
        text transcript_text
        float duration_seconds
        float stt_confidence_avg
    }
    POIS {
        uuid id PK
        uuid session_id FK
        uuid turn_id FK
        text poi_text
        enum outcome
    }
    ADJUDICATION_RESULTS {
        uuid id PK
        uuid session_id FK
        text winning_team
        float gov_total_score
        float opp_total_score
        jsonb clash_table
        jsonb speaker_scores
    }
    USER_PERFORMANCE {
        uuid id PK
        uuid user_id FK
        uuid session_id FK
        text speaker_role
        float total_score
        float argument_score
        text written_feedback
    }
    AI_CALL_LOGS {
        uuid id PK
        uuid session_id FK
        text agent_name
        text prompt_used
        text model_version
        float temperature
        text raw_output
    }
```

---

## RAG and Vector Search

**Module.** [`src/ai/tools/rag_engine.py`](src/ai/tools/rag_engine.py).

| Aspect | Detail |
|---|---|
| Embedding model | `cohere/embed-english-v3.0`, 1024 dimensions |
| Storage | `argument_embeddings.embedding VECTOR(1024)` (pgvector) |
| Distance | Cosine (`<=>` operator) |
| Filters | `match_id` (always), `side` (always), `role` (optional), `motion_category` |
| Throttled top-k | 1 / 3 / 5 by difficulty |

Each match generates its own case-prep embeddings. The AI only retrieves arguments scoped to its own match and side — no cross-match contamination, no opponent intelligence leaking across teams.

```python
results = await session.execute(
    select(ArgumentEmbedding)
    .where(ArgumentEmbedding.match_id == match_id)
    .where(ArgumentEmbedding.side == side)
    .order_by(ArgumentEmbedding.embedding.cosine_distance(query_vec))
    .limit(top_k)
)
```

---

## Redis Event Contract

### Channel pattern

```
debate:{match_id}:turns
```

The consumer uses `psubscribe("debate:*")` to fan in events from all live matches in one event loop.

### Inbound (handled)

| Event | Source | Effect |
|---|---|---|
| `START_MATCH` | Frontend via Gateway | Init `LiveMatchState`, determine first speaker, spawn first task |
| `TURN_CHANGED` | Gateway | Persist previous turn (human or AI), advance schedule, spawn next AI or notify frontend |
| `MATCH_COMPLETE` | Internal | Mark `status=finished`, `asyncio.create_task(run_adjudication_worker(...))` |

### Outbound (published)

| Event | Payload |
|---|---|
| `TURN_STARTED` | `{ event, speaker, role, side, turn_index }` |
| `AI_TOKEN` | `{ event, text }` (one per LLM token) |
| `CATCH_UP_BUFFER` | `{ event, text, is_complete, speaker_role }` (full cached speech on rejoin) |
| `AI_THOUGHT_COMPLETE` | `{ event }` |
| `MATCH_COMPLETE` | `{ event, match_id, message }` |
| `ADJUDICATION_STARTED` | `{ event }` |
| `ADJUDICATION_COMPLETE` | `{ event, verdict, gov_total_score, opp_total_score, ... }` |
| `ADJUDICATION_ERROR` | `{ event, error_message }` |

### Match state (Redis JSON)

Key: `match_state:{matchId}` · TTL: 7200 s.

```json
{
  "match_id": "...",
  "format_type": "ap",
  "status": "IN_PROGRESS",
  "current_turn_index": 3,
  
  "turn_expires_at": 1735689300,
  "is_user_connected": true,
  "last_connected_at": 1735689230,
  "ai_stream_status": "IDLE",
  "active_stream_buffer": "",
  
  "schedule": [
    { "role": "prime_minister",       "side": "government", "player_type": "ai"    },
    { "role": "leader_of_opposition", "side": "opposition", "player_type": "human" }
  ],
  "transcript": [ {...}, {...} ]
}
```

The Gateway is the only writer to `current_turn_index`. The engine reads state but never increments the turn counter.

---

## REST API

Base URL: `/api/v1` (mounted at `:8000`, fronted by the Go Gateway at `:8080/api/v1/...`).

### Auth

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/verify-supabase` | Verify Supabase JWT, return user |

### Motions and users

| Method | Path | Purpose |
|---|---|---|
| `GET` / `POST` | `/motions` | List / create motions |
| `GET` / `PATCH` | `/users/me` | Profile |
| `GET` | `/users/stats` | Aggregate match stats |

### AP and BP matches (mirrored)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/{ap\|bp}/matches` | Create match, seed CasePrep, embed arguments |
| `GET` | `/{ap\|bp}/matches` | Paginated list |
| `GET` | `/{ap\|bp}/matches/{id}` | Single match with turns |
| `PATCH` | `/{ap\|bp}/matches/{id}` | Update status |
| `GET` | `/{ap\|bp}/matches/{id}/case-prep` | AI-generated brief |
| `GET` | `/{ap\|bp}/matches/{id}/adjudication` | Final result |
| `GET` | `/{ap\|bp}/matches/{id}/adjudication/status` | Polling endpoint |

Auto-generated documentation: `http://localhost:8000/docs` (Swagger UI), `/redoc`.

---

## Tech Stack

### Core

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12 | Async ergonomics, modern type hints |
| FastAPI | 0.135 | Async-first, Pydantic v2, auto OpenAPI |
| Uvicorn | 0.42 | ASGI server |
| SQLAlchemy | 2.0 | Modern ORM with `select()` style |
| Alembic | 1.18 | Schema migrations |
| psycopg2-binary | 2.9 | Postgres driver |
| redis (asyncio) | 7.4 | Pub/sub and state |
| pgvector | 0.4 | Cosine vector search |

### AI

| Technology | Purpose |
|---|---|
| Groq (`llama-3.1-8b-instant`) | Sub-second token streaming for live turns |
| OpenAI (`gpt-4o-mini`) | Reliable case-prep fallback |
| Cohere (`embed-english-v3.0`) | 1024-dim embeddings for RAG |
| LangChain 1.2 | Streaming callback infrastructure and prompt orchestration |
| Langfuse | Trace and observability for every LLM call |

### Validation

| Technology | Purpose |
|---|---|
| Pydantic 2.12 | Schema validation |
| pydantic-settings | Typed env loading |

---

## Getting Started

### Prerequisites

- Python 3.12 or later (pinned in `pyproject.toml`)
- PostgreSQL 14 or later with the **pgvector** extension
- Redis 7 or later (local or Upstash)
- Groq, Cohere, and Supabase accounts

### Install

```bash
git clone <repository-url>
cd agora-ai-engine

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
# or with uv (faster):
# uv sync
```

### Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

### Database

```bash
# Enable pgvector once
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
alembic upgrade head
```

### Run

```bash
# Single command — starts FastAPI and the Redis consumer
python main.py
# or
uvicorn main:app --reload --port 8000
```

### Verify

```bash
curl http://localhost:8000/        # {"status": "ok"}
open http://localhost:8000/docs    # Swagger UI
```

---

## Environment Variables

`.env.example`:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/agora_ai

# Redis (local or Upstash)
REDIS_URL=rediss://default:<pass>@<host>.upstash.io:6379

# LLMs
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...           # optional fallback
COHERE_API_KEY=...

# Auth
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=eyJhbGciOi...

# Observability
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## Development

### Tests

```bash
pytest tests/unit -v
pytest tests/integration -v
pytest --cov=src tests/
```

### Lint and type-check

```bash
black src/
mypy src/
pylint src/
```

### Database

```bash
# New migration after model change
alembic revision --autogenerate -m "describe change"

# Apply
alembic upgrade head

# Roll back
alembic downgrade -1
```

### Adding a debate format

1. Create `src/ai/prompts/<format>/debater_prompts.py` with the four-phase prompt set.
2. Extend `MatchFormat` enum in `src/models/debate.py` and add the migration.
3. Add `MatchStateManager._generate_<format>_schedule()` in `src/engine/state.py`.
4. Add `src/repositories/<format>/matches.py` and `src/services/<format>/matches.py`.
5. Mount routes under `src/api/routes/v1/<format>/`.
6. Update the frontend's `FORMAT_ROLES` map and the gateway's voice ID mapping.

### Adding an LLM provider

1. Create `src/ai/clients/<provider>_client.py` exposing an async `invoke()`.
2. Wire it into `src/services/llm_service.py` selection logic.
3. Add the API key to `.env.example` and `src/core/config.py`.

---

## Deployment

The engine is a standard ASGI application. It runs anywhere `uvicorn` runs — bare metal, a VM, or any managed Python runtime. There is no container image checked into this repository; producing one is a deployment concern, not a development concern.

### Running in production

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

`--workers` must remain **1** while Redis pub/sub is the event broker. Multiple workers would each receive every event and duplicate AI generation. Horizontal scaling is gated on the Redis Streams migration listed in the [Roadmap](#roadmap).

### Resource sizing

- **CPU.** 2 vCPU is a reasonable baseline. LLM I/O is async, so CPU is consumed by embeddings, JSON serialization, and the consumer loop.
- **Memory.** 2 GB. `langchain` and the LLM client stack are memory-hungry on import.

### Pre-flight checklist

- `DATABASE_URL` points to managed Postgres with pgvector available.
- `CREATE EXTENSION vector` has been executed on the target database.
- `alembic upgrade head` has been run against the target database.
- Connection pooling (PgBouncer or Supabase Supavisor) is provisioned in front of Postgres.
- `GROQ_API_KEY` quota is sized for the expected peak concurrent matches.
- Langfuse keys are set if trace export is required.
- Exactly one instance of the consumer is running.

---

## Observability

### Structured logs

All log lines are prefixed:

```
[CONSUMER]            redis_consumer.py
[AI]                  ai_response_generator.py
[HUMAN]               Human-turn persistence
[ADJUDICATION WORKER] adjudication_worker.py
[DEBATER]             Debater agent
[ADJUDICATOR]         Adjudicator agent
[RAG]                 Retrieval engine
```

### LLM trace persistence

Every phase writes a row to `ai_call_logs`:

```
agent_name · prompt_used · model_version · temperature · raw_output
```

This is the audit trail for every AI decision in the platform — invaluable for debugging hallucinations, prompt regressions, and latency spikes.

### Langfuse integration

Set `LANGFUSE_*` env vars to stream every LLM call to Langfuse for cost, latency, and quality dashboards.

---

## Troubleshooting

<details>
<summary><strong>Consumer doesn't fire on START_MATCH</strong></summary>

Verify the gateway is publishing to the correct channel:

```bash
redis-cli psubscribe "debate:*"
```

`START_MATCH` should arrive when the frontend connects.
</details>

<details>
<summary><strong>"connection failed" on Redis</strong></summary>

For Upstash, the URL must use `rediss://` (TLS). For local Redis, `redis://`.
</details>

<details>
<summary><strong>Two AI speeches generated for one turn</strong></summary>

Multiple consumer instances are listening on the same channel. Set instance count to 1 until you migrate to Redis Streams with consumer groups.
</details>

<details>
<summary><strong>Adjudication scores don't add up</strong></summary>

Likely an LLM arithmetic hallucination. The `_recalculate_totals()` post-processor should overwrite. Check `[ADJUDICATOR] recalculated` log lines.
</details>

<details>
<summary><strong>RAG returns 0 results</strong></summary>

```sql
SELECT count(*) FROM argument_embeddings WHERE match_id = '<uuid>';
```

If zero, the embedding pipeline did not run during match creation. Check `[CASE_PREP] embedded N args` log lines.
</details>

<details>
<summary><strong>Groq 429 rate limit</strong></summary>

The free tier rate-limits aggressively. Options:

- Upgrade the Groq plan.
- Add exponential backoff in `groq_client.py`.
- Switch debater to OpenAI fallback via `llm_service.py`.
</details>

---

## Roadmap

| Area | Today | Next |
|---|---|---|
| Event broker | Redis pub/sub (single instance) | Redis Streams with consumer groups, horizontal scaling |
| Adjudication | Single-pass five-phase | Ensemble of three adjudicators, majority vote |
| RAG corpus | Match-scoped only | Cross-match knowledge with strict isolation |
| Personality | Three difficulty bands | User-defined judge and opponent personalities |
| Spectator mode | Solo only | Live broadcast and queueable hub |
| Multilingual | English-only | Cohere multilingual embeddings, Hindi and Tamil debates |

---

## Further Reading

- [`agora_system_architecture.md`](../agora_system_architecture.md) — full ecosystem architecture
- [`production_grade_architecture.md`](../production_grade_architecture.md) — production hardening notes
- [`agora-frontend`](../agora-frontend) — sibling Next.js arena UI
- [`agora-gateway`](../agora-gateway) — sibling Go socket broker
- [Groq API](https://console.groq.com/docs)
- [pgvector](https://github.com/pgvector/pgvector)
- [LangChain async callbacks](https://python.langchain.com/docs/modules/callbacks/)

---

<div align="center">

**Built with 🧠 in Python · The Brain of Agora**

</div>
