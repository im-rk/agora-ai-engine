# Agora AI Engine – Production Architecture & Rebuild Guide

This document provides a comprehensive, FAANG-grade architectural analysis of the **Agora AI Engine** repository. It details exactly how the repository functions internally, how it interacts with the broader distributed system, and provides a step-by-step rebuilding guide.

---

## 1. Repository Role in Overall System

The `agora-ai-engine` is the **core intelligence and state machine** of the Agora real-time debate platform. While the Go Gateway acts as the high-throughput socket broker and STT/TTS mediator, this Python service serves as the "brain".

### Pipeline Context
`User Audio → Frontend → Go Gateway → STT → Redis Pub/Sub → [ THIS PYTHON ENGINE ] → Redis Pub/Sub → Go Gateway → TTS → Frontend`

### Core Responsibilities
1. **Debate State Management**: Bootstraps the debate, calculates speaker schedules, and tracks what happens (turns, transcript, Points of Information (POIs)) using Redis as the real-time store.
2. **AI Action Orchestration**: Houses the Multi-Agent architecture to generate highly structured and contextually aware debate arguments and decisions:
   - *Prep Coach*: Post-match/Pre-match case preparation + creating semantic embeddings.
   - *Debater Agent*: Generates real-time, four-phase debate responses while streaming tokens.
   - *Sniper Agent*: Decides in milliseconds whether to accept or decline human POIs.
   - *Adjudicator Agent*: Grades the entire match after it concludes.
3. **Data Persistence (Source of Truth)**: Commits permanent records to Postgres (via SQLAlchemy & Supabase) for analytics, history, and RAG. RAG utilizes `pgvector`.
4. **Real-Time Streaming Generator**: Pushes individual LLM tokens to Redis channels to give users typewriter-effect responses over sockets.

### Data Contracts
- **Inputs**: STT text chunks (via Go), User Setup Data (via HTTP REST), Redis Pub/Sub commands (`START_MATCH`, `TURN_CHANGED`, `POI_OFFERED`).
- **Outputs**: Streaming text tokens, State Patches (to Redis), Final scores/results.

---

## 2. Full Folder & File Breakdown

### Root Directory
- `main.py`: The FastAPI application entrypoint. Configures middlewares, registers routes, and manages the application lifecycle (starts the Redis consumer background task).
- `alembic/`: Database migration definitions for SQLAlchemy.
- `.env` / `pyproject.toml` / `requirements.txt`: Environment and dependency configurations.

### `src/` - Core Source Code Directory

#### `src/api/` - HTTP Interface
- `rest/matches.py`: HTTP routes for starting matches (`POST /`), retrieving case prep (`GET /{match_id}/prep`), and manually requesting generation.
- `rest/history.py`: Retrieves debate session results and user histories.
- `dependencies.py`: FastAPI Dependency Injection (e.g., getting DB session, getting current user context).

#### `src/workers/` - Event Consumers
- `redis_consumer.py`: The central event loop. Uses `redis.psubscribe("debate:*")` to listen to state changes from Go and fires off concurrent asyncio tasks to run AI pipelines without blocking the event loop.

#### `src/engine/` - State & Rules Machine
- `state.py`: Implements `MatchStateManager`. Houses the layout of the `LiveMatchState` logic: fetching and mutating the Redis JSON state.
- `rules.py`: Hardcoded time structures/limit rule-sets (BP vs. AP rules: e.g., when a POI window opens/closes). Contains `FormatRules`.

#### `src/ai/` - AI Architecture (LangChain & Integrations)
- `agents/debater.py`: 4-Phase RAG Debater engine (Phase 1: Clash Matrix, Phase 2: Queries, Phase 3: pgvector Retrieval, Phase 4: LangChain Streaming).
- `agents/prep_coach.py`: Initial setup AI that creates arguments mapped against a specific format.
- `agents/sniper.py`: Short-circuiting low-latency agent evaluating incoming POIs. 
- `agents/adjudicator.py`: GPT-4o-mini powered grading framework that recalculates totals safely at match's end.
- `clients/`: Contains singletons and wrappers for LLM providers (`groq_client.py`, `openai_client.py`).
- `callbacks/redis_stream.py`: LangChain callback handler pushing `on_llm_new_token` to Redis pub/sub.
- `prompts/`: Template repository containing system messages for the agents.
- `tools/rag_engine.py`: Encapsulates `pgvector` distance/cosine similarity searches. 

#### `src/services/` - Domain Logic Layer
- `match_service.py`, `case_prep_service.py`, `grading_service.py`: Business logic that bridges HTTP/Workers with the Database. Keeps endpoints thin.

#### `src/repositories/` - Data Access Layer (DAL)
- `debate_repo.py`, `case_prep_repo.py`, `results_repo.py`: SQL wrappers keeping raw SQLAlchemy queries extracted away from business logic.

#### `src/schemas/` & `src/models/`
- `schemas/`: Pydantic models for HTTP and Redis JSON layouts (`state_schema.py`, `debate_schema.py`).
- `models/`: SQLAlchemy ORM definitions (`setup.py`, `debate.py`, `user.py`).

---

## 3. Internal Architecture

The application strictly adheres to **Domain-Driven Design (DDD)** combined with an **Event-Driven Microservices** behavior.

1. **Separation of Concerns**: 
   - HTTP routes do nothing but validate payloads and call Services.
   - Services execute domain logic and call Repositories.
   - AI Agents are decoupled entirely from the web layer and run via background workers.
2. **Actor-Based Asynchrony**: The `redis_consumer.py` acts as an event loop actor. Instead of keeping a REST HTTP connection open for 10 minutes while a debate happens, control flow maps to independent `pub/sub` events triggered by Go or the human user.
3. **Polyglot Storage**: 
   - PostgreSQL (Relational consistency).
   - pgvector (Semantic AI Context).
   - Redis Memory (Ephemeral fast-moving match states bridging Go and Python).

---

## 4. Execution Flow (Step-by-Step)

### A. Match Startup
1. **Frontend** POSTs `start_new_match` payload.
2. HTTP Route `api/rest/matches.py` -> `match_service.start_new_match()`.
3. SQLAlchemy creates a DB `DebateSession` record. 
4. The Service invokes `state_manager.initialize_match()`, creating a strict turn schedule and writing it to Redis key `match_state:{id}`.
5. `prepare_case` is called triggers the **Prep Coach Agent**, fetching the `CasePrep` arguments, building vector embeddings, and storing them in `pgvector`.
6. API responds `200 OK`. 

### B. Live Debate Loop
1. **Human/Frontend** or **Go** fires `START_MATCH` into Redis format `debate:{id}:turns`.
2. Python `redis_consumer.start_redis_consumer` intercepts. If the first speaker in `state.schedule[...].player_type == "ai"`, Python fires `generate_ai_response()`.
3. **Debater Agent Pipeline** initiates phase 1 (Parse state) -> phase 2 (Queries) -> phase 3 (Retrieve from pgvector) -> phase 4 (Groq Stream).
4. As Groq generates words, `RedisStreamingCallbackHandler` catches them and does `pubsub.publish` to `debate:{speaker_id}:response`. Go forwards these words to Frontend via WebSockets.
5. Turn complete. State updated. Python sets `TURN_STARTED` (human).
6. Human talks. STT feeds into Go. Go updates `current_turn_index` natively and publishes `TURN_CHANGED`.
7. Python picks it up, validates it's the AI's turn again, repeats loop.

### C. The Sniper Interaction (POI)
1. Human clicks "Offer POI". Redis gets `POI_OFFERED`.
2. Python intercepts. Worker invokes `SniperAgent.evaluate_incoming_poi()`.
3. Sniper checks `rules.py` hard limits (e.g. `is_poi_window_open()`). If illegal, instantly declines.
4. If legal, Groq LLM evaluates the transcript.
5. Python outputs `POI_ACCEPTED` or `POI_DECLINED` payloads back to Redis.

### D. Adjudication
1. Turn index exceeds schedule max.
2. `redis_consumer` fires `trigger_adjudication`.
3. `AdjudicatorAgent` utilizes `GPT-4o-mini` with the full `transcript` & `POI record`.
4. Verdict recalculates in Python. Saved structurally to `user_performance_table`.
5. Publishes `MATCH_COMPLETE` event.

---

## 5. Data Flow & State Management

**The State Ownership Contract**: 
- The schema structure is definitively owned by the `LiveMatchState` Pydantic model (`src/schemas/state_schema.py`).
- **Python** populates the complex structure (Full schedule array, POI records, transcript text).
- **Go Gateway** is allowed to structurally patch only the `current_turn_index` integer via Redis Map patch.
- Python always requests the freshly merged state block using `LiveMatchState.model_validate_json()` upon a state notification.

**RAG Storage (pgvector)**:
- Post-initialization, `ArgumentEmbedding` stores vectorized representations of generated human/AI responses using Cohere embeddings. `vector(1024)`. Used exclusively for phase 3 of the AI generation pipeline to surface counter-arguments quickly on the fly without heavy multi-agent queries.

---

## 6. Real-Time Streaming Logic

Python leverages LangChain `AsyncCallbackHandler` mechanism:
```python
class RedisStreamingCallbackHandler(AsyncCallbackHandler):
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        await self.redis_client.publish(
            self.channel, 
            json.dumps({"event": "TOKEN", "text": token})
        )
```
- A generation invocation to Groq is attached via `config={"callbacks": [callback]}`. 
- Python buffers absolutely nothing. Groq Token emitted → LangChain Event → Redis PUBLISH.
- By utilizing `redis.asyncio`, streaming out 100 tokens a second runs completely non-blocking, allowing Sniper POIs to be intercepted even while the Debater Agent is mid-sentence.

---

## 7. Integration Points

- **Go Gateway**: Communicates entirely via structurally formalized Redis `psubscribe("debate:*")` topic streams. No direct HTTP traffic flows between Python and Go.
- **Frontend**: Primarily REST HTTP calls for match initiation, profile logic, and viewing past case preps. Real-time actions are proxied via the Go WebSockets. 
- **AI Services**: Groq specifically utilized where speed is paramount (Streaming generation, SNIPER interactions). OpenAI used strictly where semantic structure must be guaranteed (Adjudicator outputting heavily nested JSON arrays and objects). Cohere used for Vector generation.
- **Postgres / Supabase**: Uses SQLAlchemy ORM. Exposes `user.id` references matching the authentication service on Supabase.

---

## 8. Code Deep Dive: `redis_consumer.start_redis_consumer()`

This is the heartbeat of the application.
1. `pubsub.psubscribe("debate:*")` - Pattern matches all match events.
2. Extracts match IDs (`debate:{match_id}:...`).
3. Acts as a Master Switch Statement.
   - `if action == "START_MATCH":` - Evaluates `state.schedule`. Kicks off generation if the agent is side-aligned as speaker 1.
   - `elif action == "TURN_CHANGED":` - Pulls modified JSON from Redis. Checks if game over (`index >= len(schedule)`). If game active and it's AI turn, spawns background task.
   - `elif action == "POI_OFFERED":` - Immediately dispatches Sniper on the active turn block.

**Important**: Because operations like `generate_ai_response` take seconds (multi-phase), they are wrapped in `asyncio.create_task()`. The consumer loop *instantly* returns to listening. 

---

## 9. Industry Practices Used

- **Stateless AI Actors**: `DebaterAgent` and `SniperAgent` hold no instance variables. They simply execute functions passed with parameters. Highly horizontal scalability.
- **RAG Pre-computation**: The application does not generate evidence on the fly during the match—all evidence is created by `Prep Coach` and indexed in `pgvector` before the match, allowing the `DebaterAgent`'s phase 3 to execute in <50ms.
- **Dual-Model Architecture**: Matching Groq (Speed/Llama3, Fast TTFT) with OpenAI (Accuracy/GPT4o, Structured Validation) optimized properly for edge cases. 
- **Hard-Rule Guardrails**: The Sniper agent runs logic like `if pois_accepted_count >= limit: return decline` **before** calling the LLM. This prevents Hallucination overrides and saves API bandwidth.
- **LangFuse**: Decorates logs and prompt payloads across the whole engine allowing full debugging and tracing observability inside production.

---

## 10. Missing / Weak Areas

- **Bottlenecks/Risks**: 
  1. The Redis consumer pattern `psubscribe` inside a single event loop is acceptable for 1-100 matches, but scales poorly geographically. As load increases, this needs to be decoupled via a Celery queue or Redis Streams (`XREADGROUP`) to enforce exactly-once delivery and distributed cluster consumption. Right now, running 2 instances of this python server would duplicate generation tasks!
  2. The LLM handles mathematics poorly in the Adjudicate prompt; there's a good hack implemented (`_recalculate_totals`), but generating raw numeric data from large LLMs always remains inherently risky.
- **Error Handling**: `json.JSONDecodeError` inside the redis event loop uses `pass`. Malformed packets from Go sink into a black hole with no external visibility.

---

## 11. Phase-by-Phase Rebuild Guide

If you need to replicate this repository's behavior from a blank directory, follow these strict phases:

### Phase 1: Database & Configuration Foundations
1. Define Pydantic settings parsing environment variables (`.env`).
2. Create SQLAlchemy definitions: `User`, `DebateSession`, `CasePrep`, `Turn`, `POI` tables.
3. Attach `pgvector` to cases by creating `ArgumentEmbedding` with `Vector(1024)`.
4. Initialize Alembic migrations and verify DB structure mounts.

### Phase 2: Schema & State Modeling (The Rulebook)
1. Build `state_schema.py::LiveMatchState` containing Turn arrays, POI arrays, and basic booleans.
2. Implement `state.py::MatchStateManager`. Write simple Async Redis get/set tools that validate JSON into Pydantic on fetch, and dump json on save.
3. Implement `rules.py` dict to hardcode time caps, lengths, and POI windows.

### Phase 3: The AI Integrations
1. Create wrapper clients for Groq and OpenAI.
2. Build the LLM chains:
    - **Adjudicator**: Prompts requiring struct output.
    - **Prep Coach**: Standard Q&A generating JSON.
    - **Sniper**: Low temp, binary output decisions based on transcript chunks.
3. Build the `pgvector` RAG queries wrapped in `tools/rag_engine.py` (Embedding via Cohere).
4. Construct the **Debater Agent** pipeline tying it all together.

### Phase 4: Core Services & Web APIs
1. Create `match_service.py` to trigger setup functions.
2. Create `case_prep_service` to generate cases and save chunks into the embedding tables.
3. Tie these directly to thin FastAPI `rest/*.py` REST endpoints.

### Phase 5: Event Subsystem (Streaming & WebSockets Proxying)
1. Write `callbacks/redis_stream.py` tracking token emission. Connect to Debater Agent configuration.
2. Construct the central `workers/redis_consumer.py`. Route JSON PubSub messages based on the string value of the `action` field. 
3. Tie `redis_consumer` loops into the `lifespan` hook of `main.py` so the task boots upon `uvicorn` startup. 
4. Scale test. Ensure connections handle drops smoothly.
