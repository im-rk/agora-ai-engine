# Agora AI Scripts

Comprehensive testing and validation scripts for the Agora AI debate engine.

## 📋 Script Categories

### 1. AP Architecture Validation Scripts
Validate the Asian Parliamentary (AP) debate engine implementation:

```bash
# Run all AP validations
python -m scripts.run_all_validations

# Or run individual validations
python -m scripts.validate_architecture
python -m scripts.validate_services
python -m scripts.validate_schemas
python -m scripts.validate_routes
python -m scripts.validate_ap_flow
python -m scripts.validate_imports
```

See [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) for complete details.

---

### 2. Sandbox Testing Scripts

Comprehensive integration testing for all components of the Agora AI debate engine. These scripts test individual components and the full pipeline without mocks, using real connections to Upstash Redis, Supabase PostgreSQL, and Groq API.

## Testing Order

Run these tests in sequence to progressively validate the system:

### 1. test_redis_connection.py - Redis
```bash
python -m scripts.test_redis_connection
```
**Tests:** 
- Upstash Redis connectivity
- PING/SET/GET operations
- PubSub channel publishing

**Expected:** Connection succeeds, can SET/GET keys, publish to channels

---

### 2. test_state_manager.py - State Management
```bash
python -m scripts.test_state_manager
```
**Tests:**
- Match state initialization
- Add turns to transcript
- Persist state to Redis
- Retrieve state from Redis
- Data integrity verification

**Expected:** States saved and retrieved with intact transcript data

---

### 3. test_groq_client.py - LLM Connectivity
```bash
python -m scripts.test_groq_client
```
**Tests:**
- Non-streaming LLM calls
- Streaming LLM calls
- Client caching (lru_cache)

**Expected:** LLM API responds with debate-related content, caching works

---

### 4. test_rag_engine.py - Evidence Retrieval (pgvector)
```bash
python -m scripts.test_rag_engine
```
**Tests:**
- pgvector connection to Supabase
- Retrieve counter-arguments
- Retrieve supporting arguments
- Vector similarity scoring

**Expected:** Successfully queries pgvector, returns ranked results (if DB has data)

---

### 5. test_debater_pipeline.py - Full AI Pipeline
```bash
python -m scripts.test_debater_pipeline
```
**Tests:**
- Phase 1: Clash matrix parsing
- Phase 2: Query synthesis
- Phase 3: Evidence retrieval
- Phase 4: Response generation (with streaming)
- Full orchestration

**Expected:** All 4 phases complete, generates coherent debate response

---

### 6. test_case_prep_storage.py - Case Prep & RAG
```bash
python -m scripts.test_case_prep_storage
```
**Tests:**
- Create motion record
- Generate case prep
- Store arguments as embeddings in pgvector
- Retrieve embeddings via RAG
- Verify data integrity

**Expected:** Case prep saved, embeddings stored, retrieval works

---

### 7. test_e2e_flow.py - End-to-End Tests
```bash
python -m scripts.test_e2e_flow
```
**Tests:**
- Full workflow: User -> Motion -> Session -> AI Response
- Redis state persistence
- Supabase Turn record creation
- AI call logging to ai_call_logs table

**Expected:** Complete flow succeeds, records in both Redis and Supabase

---

## Running All Tests

```bash
# Run all tests sequentially
python -m scripts.test_redis_connection
python -m scripts.test_state_manager
python -m scripts.test_groq_client
python -m scripts.test_rag_engine
python -m scripts.test_debater_pipeline
python -m scripts.test_case_prep_storage
python -m scripts.test_e2e_flow
```

## Troubleshooting

| Test | Issue | Solution |
|------|-------|----------|
| 1-3 | API key errors | Verify `.env` has `GROQ_API_KEY`, `REDIS_URL` |
| 4-6 | DB connection errors | Check `DATABASE_URL` points to valid Supabase |
| 4 | No results returned | Populate `argument_embeddings` table with test data first |
| 5-7 | LLM errors | Check Groq API quota, rate limits, model availability |

## Output Format

All tests use standardized output format:
- `[PASS]` - Test passed successfully
- `[FAIL]` - Test failed with error
- `[WARN]` - Warning or non-critical issue

## Next: Unit Testing

After all sandbox tests pass, create unit tests in `tests/unit/` with mocks:

```
tests/
├── unit/
│   ├── test_debater_phases_mocked.py     # Mock Groq, RAG
│   ├── test_state_manager_mocked.py      # Mock Redis
│   ├── test_case_prep_mocked.py          # Mock DB
│   └── test_redis_consumer_mocked.py     # Mock everything except logic
└── integration/
    └── (existing integration tests)
```

## Integration Testing Strategy

| Layer | Testing Type | Mock? | When? |
|-------|-------------|-------|-------|
| Individual Component | Sandbox (scripts/) | No | First (these) |
| Component Units | Unit Tests | Yes | After sandbox passes |
| Full Workflow | Integration Tests | No | Final validation |

---

**Status:** All 7 sandbox tests should pass before proceeding to unit tests.
