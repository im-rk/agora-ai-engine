# WebSocket Rejoin Feature - Implementation Plan v2

**Status**: Architecture Clarified, Ready for Implementation  
**Created**: May 14, 2026  
**Approach**: Cache + Replay with Timer Pause/Resume  

---

## 1. Overview of the Three-System Architecture

```
┌──────────────────┐
│    FRONTEND      │  Next.js + Zustand
│ (React App)      │  • Timer pause/resume (local state)
│                  │  • WebSocket to Gateway only
└────────┬─────────┘
         │ WS
         │ (Frontend ↔ Gateway)
┌────────▼──────────────────────────┐
│      GATEWAY (Go)                  │
│ Port 8080                          │
│ • Gorilla WebSocket                │
│ • Deepgram STT/TTS                 │
│ • Proxy to Backend                 │
└────────┬──────────────────────────┘
         │ REST API
         │ (Gateway ↔ Backend)
┌────────▼──────────────────────────┐
│      BACKEND (FastAPI)             │
│ Port 8000                          │
│ • State management (Redis)         │
│ • LLM orchestration (Groq)         │
│ • Tournament logic                 │
└────────────────────────────────────┘
```

**Critical Rule**: Frontend and Backend communicate ONLY through Gateway via WebSocket.

---

## 2. Current State (What's Already Working)

### ✅ Backend - Phase 1-3 Complete

**State Schema** (`src/schemas/state_schema.py`):
- ✅ `is_user_connected`: Boolean (connection tracking)
- ✅ `last_connected_at`: Unix timestamp (last connection time)
- ✅ `ai_stream_status`: IDLE | STREAMING | PAUSED | COMPLETED
- ✅ `active_stream_buffer`: Accumulated tokens from AI generation

**State Manager** (`src/engine/state.py`):
- ✅ `initialize_match()` sets initial state with all fields
- ✅ `get_state()` retrieves from Redis
- ✅ `update_state()` persists to Redis with 2-hour TTL

**Token Buffering** (`src/ai/callbacks/redis_stream.py`):
- ✅ Callback handler accepts `state` and `state_manager`
- ✅ `on_llm_new_token()` appends tokens to `active_stream_buffer`
- ✅ Persists state after each token

**Event Handlers** (`src/workers/redis_consumer.py`):
- ✅ `DISCONNECT` handler: marks offline, pauses if human
- ✅ `REJOIN_MATCH` handler: sends CATCH_UP_BUFFER

### ❌ What's NOT Yet Done

**Backend Phase 4**:
- ❌ REST endpoint: `GET /matches/{match_id}/state` (NEW)
- ❌ Timer calculation logic update (needs refactor)

**Gateway Phase 5**:
- ❌ WebSocket message handler for `GET_MATCH_STATE`
- ❌ WebSocket message handler for `SYNTHESIZE_CACHED_SPEECH`

**Frontend Phase 6**:
- ❌ Rejoin protocol implementation
- ❌ Timer pause/resume logic
- ❌ TTS playback for cached speech

---

## 3. Timer Model Refactor (IMPORTANT CHANGE)

### OLD Model (turn_expires_at - REMOVE)
```python
turn_expires_at: int  # Absolute Unix timestamp when turn expires
time_remaining_seconds: @property  # Calculated from turn_expires_at - now()
```

### NEW Model (match-based - REPLACE)
```python
match_started_at: int          # Unix timestamp when match began (once)
match_duration_seconds: int    # Total match duration (e.g., 1800 for 30-min AP)
current_turn_index: int        # Current speaker index (already exists)
current_turn_duration_seconds: int  # Duration of CURRENT speaker (e.g., 300 for 5 mins)
total_offline_duration: int    # Accumulates all disconnection periods

time_remaining_seconds: @property
  calculated as:
    elapsed = now() - match_started_at
    active_time = elapsed - total_offline_duration
    turn_time_remaining = current_turn_duration_seconds - active_time
    return max(0, turn_time_remaining)
```

**Key Benefit**: 
- Frontend timer pauses locally (no network calls)
- Backend tracks ONLY actual active time
- Offline duration accumulates across multiple disconnects
- No deadline extension needed; just account for inactive time

---

## 4. Backend Changes (Phase 4)

### 4.1 Update State Schema - `src/schemas/state_schema.py`

**Remove**:
```python
turn_expires_at: Optional[int] = None
```

**Add**:
```python
match_started_at: int                    # Unix timestamp when match began
match_duration_seconds: int              # Total duration (computed from format + schedule)
current_turn_duration_seconds: int       # Duration of current speaker's turn
total_offline_duration: int = 0          # Accumulates offline periods
```

**Update @property**:
```python
@property
def time_remaining_seconds(self) -> int:
    """Calculate remaining time based on active time (excluding offline periods)."""
    now = int(datetime.now(timezone.utc).timestamp())
    elapsed = now - self.match_started_at
    active_time = elapsed - self.total_offline_duration
    remaining = self.current_turn_duration_seconds - active_time
    return max(0, remaining)
```

### 4.2 Update State Manager - `src/engine/state.py`

**In `initialize_match()`, replace**:
```python
# OLD
turn_expires_at=now + turn_duration

# NEW
match_started_at=now,
match_duration_seconds=self._calculate_match_duration(format_type),
current_turn_duration_seconds=300,  # AP = 5 mins, BP = vary
total_offline_duration=0
```

**Add helper method**:
```python
def _calculate_match_duration(self, format_type: str) -> int:
    """Calculate total match duration based on format."""
    if format_type.lower() in ["asian parliamentary", "ap"]:
        return 6 * 300  # 6 speakers × 5 mins = 1800 seconds
    elif format_type.lower() in ["british parliamentary", "bp"]:
        return 8 * 300  # 8 speakers × 5 mins (simplified, varies in BP)
    else:
        return 10 * 300  # Default 50 mins
```

### 4.3 Update TURN_CHANGED Handler - `src/workers/redis_consumer.py`

When a turn changes, update `current_turn_duration_seconds`:
```python
# In TURN_CHANGED event handler
if state.current_turn_index < len(state.schedule):
    # Update duration for this speaker (may vary in BP)
    state.current_turn_duration_seconds = 300  # Simplified; could be speaker-specific
    await state_manager.update_state(state)
```

### 4.4 Update REJOIN_MATCH Handler - `src/workers/redis_consumer.py`

**Replace deadline extension logic with offline accumulation**:
```python
elif action == "REJOIN_MATCH":
    state = await state_manager.get_state(match_id)
    if not state:
        # ... error handling
        continue
    
    now = int(datetime.now(timezone.utc).timestamp())
    offline_duration = now - state.last_connected_at
    
    # ACCUMULATE offline time (don't extend deadline)
    state.total_offline_duration += offline_duration
    logger.info(
        f"[CONSUMER] Accumulated offline: {offline_duration}s, "
        f"total: {state.total_offline_duration}s"
    )
    
    # Mark reconnected
    state.is_user_connected = True
    state.last_connected_at = now
    state.status = "IN_PROGRESS"
    await state_manager.update_state(state)
    
    # Send catch-up buffer if AI was generating
    current_speaker = state.schedule[state.current_turn_index]
    if (current_speaker.player_type == "ai" and 
        state.active_stream_buffer):
        
        await client.publish(channel, json.dumps({
            "event": "CATCH_UP_BUFFER",
            "text": state.active_stream_buffer,
            "is_complete": (state.ai_stream_status == "COMPLETED"),
            "speaker_role": current_speaker.role
        }))
    
    # ... rest of handler
```

### 4.5 Create State REST Endpoint - NEW FILE `src/api/routes/v1/state.py`

```python
"""
Match State Endpoint - For Frontend Rejoin Protocol

When user disconnects and reconnects, they fetch full match state
to reconstruct UI and determine what audio needs TTS.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, status
from src.engine.state import state_manager
from src.schemas.common import APIResponse, APIStatusCode

router = APIRouter()

@router.get(
    "/matches/{match_id}/state",
    response_model=APIResponse,
    summary="Get current match state for rejoin",
    tags=["Match State"]
)
async def get_match_state(
    match_id: str = Path(..., description="Match ID")
):
    """
    Get full match state for rejoin protocol.
    
    Returns:
    - active_stream_buffer: Cached AI speech (for TTS)
    - match_started_at: When match began
    - total_offline_duration: How much time user was offline
    - current_turn_index: Current speaker
    - schedule: All speakers
    - is_user_connected: Connection status
    - ai_stream_status: AI generation state
    - time_remaining_seconds: Time left for current speaker
    
    Frontend uses this to:
    1. Reconstruct match UI
    2. Get cached speech for TTS synthesis
    3. Resume timer from correct position
    """
    try:
        state = await state_manager.get_state(match_id)
        
        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Match {match_id} not found"
            )
        
        # Return full state so frontend can rejoin
        return APIResponse(
            status=APIStatusCode.SUCCESS,
            message="Match state retrieved",
            data={
                "match_id": state.match_id,
                "format_type": state.format_type,
                "status": state.status,
                "current_turn_index": state.current_turn_index,
                "schedule": [s.model_dump() for s in state.schedule],
                "match_started_at": state.match_started_at,
                "match_duration_seconds": state.match_duration_seconds,
                "current_turn_duration_seconds": state.current_turn_duration_seconds,
                "total_offline_duration": state.total_offline_duration,
                "time_remaining_seconds": state.time_remaining_seconds,
                "is_user_connected": state.is_user_connected,
                "ai_stream_status": state.ai_stream_status,
                "active_stream_buffer": state.active_stream_buffer,  # For TTS
                "transcript": state.transcript,
            }
        )
    
    except Exception as e:
        logger.error(f"Error fetching match state: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve match state"
        )
```

### 4.6 Register State Router - Update `src/api/routes/v1/__init__.py`

```python
from .state import router as state_router

v1_router.include_router(state_router, prefix="", tags=["Match State"])
```

---

## 5. Gateway Changes (Phase 5)

### 5.1 WebSocket Message Handler for Rejoin - `gateway/websocket/handlers.go` (NEW)

```go
// Handle GET_MATCH_STATE message from frontend
// Frontend sends: { "event": "GET_MATCH_STATE", "match_id": "..." }
func handleGetMatchState(ws *websocket.Conn, msg map[string]interface{}) {
    matchID := msg["match_id"].(string)
    
    // Call backend REST API
    resp, err := http.Get(fmt.Sprintf("http://backend:8000/api/v1/matches/%s/state", matchID))
    if err != nil {
        sendError(ws, "Failed to fetch match state")
        return
    }
    defer resp.Body.Close()
    
    var stateResponse map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&stateResponse)
    
    // Send state back to frontend via WebSocket
    ws.WriteJSON(map[string]interface{}{
        "event": "MATCH_STATE_RESPONSE",
        "data": stateResponse["data"],
    })
}
```

### 5.2 WebSocket Message Handler for TTS - `gateway/websocket/handlers.go` (NEW)

```go
// Handle SYNTHESIZE_CACHED_SPEECH message from frontend
// Frontend sends: { 
//   "event": "SYNTHESIZE_CACHED_SPEECH", 
//   "text": "...", 
//   "speaker": "..." 
// }
func handleSynthesizeCachedSpeech(ws *websocket.Conn, msg map[string]interface{}) {
    text := msg["text"].(string)
    speaker := msg["speaker"].(string)
    
    // Call Deepgram TTS API
    audioStream, err := deepgram.Synthesize(text, "en-US")
    if err != nil {
        sendError(ws, "TTS synthesis failed")
        return
    }
    
    // Stream audio back to frontend
    for audioChunk := range audioStream {
        ws.WriteMessage(websocket.BinaryMessage, audioChunk)
    }
    
    // Signal end of audio
    ws.WriteJSON(map[string]interface{}{
        "event": "AUDIO_COMPLETE",
        "speaker": speaker,
    })
}
```

### 5.3 Update Main Message Router - `gateway/websocket/handlers.go`

```go
func handleWebSocketMessage(ws *websocket.Conn, msg map[string]interface{}) {
    event := msg["event"].(string)
    
    switch event {
    // Existing handlers
    case "START_SPEECH":
        handleStartSpeech(ws, msg)
    case "SPEECH_CHUNK":
        handleSpeechChunk(ws, msg)
    
    // NEW handlers for rejoin
    case "GET_MATCH_STATE":
        handleGetMatchState(ws, msg)
    case "SYNTHESIZE_CACHED_SPEECH":
        handleSynthesizeCachedSpeech(ws, msg)
    }
}
```

---

## 6. Frontend Changes (Phase 6)

### 6.1 Rejoin Protocol Hook - `frontend/hooks/useRejoinProtocol.ts` (NEW)

```typescript
import { useEffect, useRef } from 'react';
import { useMatchStore } from '@/store/matchStore';
import { useTimerStore } from '@/store/timerStore';

export function useRejoinProtocol() {
  const { matchId } = useMatchStore();
  const { setMatchState, setTotalOfflineDuration } = useTimerStore();
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    const handleReconnect = async () => {
      try {
        // Step 1: Send WebSocket message to Gateway
        ws.send(JSON.stringify({
          event: "GET_MATCH_STATE",
          match_id: matchId,
        }));

        // Step 2: Wait for MATCH_STATE_RESPONSE from Gateway
        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          
          if (msg.event === "MATCH_STATE_RESPONSE") {
            const state = msg.data;
            
            // Step 3: Reconstruct match UI from state
            setMatchState(state);
            setTotalOfflineDuration(state.total_offline_duration);
            
            // Step 4: Resume timer from correct position
            // Timer pauses locally on disconnect, resumes here
            resumeTimer(state.time_remaining_seconds);
            
            // Step 5: Check if AI was speaking and buffer exists
            if (state.active_stream_buffer && state.ai_stream_status !== "IDLE") {
              // Step 6: Request TTS for cached buffer
              ws.send(JSON.stringify({
                event: "SYNTHESIZE_CACHED_SPEECH",
                text: state.active_stream_buffer,
                speaker: state.schedule[state.current_turn_index].role,
              }));
              
              // Step 7: Play audio when it arrives
              playAudio(audioStream);
            }
          }
        };
      } catch (error) {
        console.error("Rejoin failed:", error);
        // Retry in 2 seconds
        reconnectTimeoutRef.current = setTimeout(handleReconnect, 2000);
      }
    };

    // Listen to WebSocket reconnect event
    window.addEventListener("websocket:connected", handleReconnect);
    
    return () => {
      window.removeEventListener("websocket:connected", handleReconnect);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [matchId]);
}
```

### 6.2 Timer Pause/Resume - `frontend/hooks/useDebateTimer.ts` (UPDATE)

```typescript
export function useDebateTimer() {
  const [timeRemaining, setTimeRemaining] = useState(300);
  const [isPaused, setIsPaused] = useState(false);
  const timerRef = useRef<NodeJS.Timeout>();

  // Listen to WebSocket connect/disconnect events
  useEffect(() => {
    const handleDisconnect = () => {
      setIsPaused(true);  // Pause timer locally
      clearInterval(timerRef.current);
    };

    const handleReconnect = (event: CustomEvent) => {
      const { timeRemaining: newTime } = event.detail;
      setTimeRemaining(newTime);  // Update from server
      setIsPaused(false);  // Resume counting down
    };

    window.addEventListener("websocket:disconnected", handleDisconnect);
    window.addEventListener("websocket:reconnected", handleReconnect);

    return () => {
      window.removeEventListener("websocket:disconnected", handleDisconnect);
      window.removeEventListener("websocket:reconnected", handleReconnect);
    };
  }, []);

  // Timer countdown (when connected)
  useEffect(() => {
    if (isPaused || timeRemaining <= 0) return;

    timerRef.current = setInterval(() => {
      setTimeRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, [isPaused, timeRemaining]);

  return { timeRemaining, isPaused };
}
```

---

## 7. Data Flow Example - User Disconnect & Rejoin

### Timeline

```
T=0:00  Match starts
        Backend: match_started_at = 1715340000 (Unix timestamp)
        Backend: total_offline_duration = 0
        Frontend: Timer shows 5:00 (300 seconds)

T=2:00  AI speaking: "The economy is crucial..."
        Backend: active_stream_buffer += tokens
        Pub/Sub streams: AI_TOKEN events
        Frontend: Timer shows 3:00 (300 seconds remaining)

T=3:30  USER DISCONNECTS (network failure)
        ├─ Frontend: WebSocket closes
        ├─ Frontend: Timer PAUSES at 2:30 remaining
        ├─ Backend: DISCONNECT event received
        ├─ Backend: is_user_connected = false
        └─ AI keeps generating naturally

T=5:00  AI finishes speech
        Backend: active_stream_buffer = "The economy is crucial for..."
        Backend: ai_stream_status = "COMPLETED"

T=8:00  USER RECONNECTS (network restored)
        ├─ Frontend: WebSocket reconnects
        ├─ Frontend: Timer still shows 2:30 (paused)
        ├─ Frontend sends: GET_MATCH_STATE via Gateway
        │
        └─ Backend processes REJOIN_MATCH:
            ├─ Calculate: offline_duration = 8:00 - 3:30 = 270 seconds
            ├─ Accumulate: total_offline_duration += 270 (now 270)
            ├─ Calculate time_remaining:
            │  elapsed = 8:00 - 0:00 = 480 seconds
            │  active_time = 480 - 270 = 210 seconds
            │  remaining = 300 - 210 = 90 seconds (1:30)
            ├─ Send REST response with active_stream_buffer
            │
            └─ Frontend receives state:
                ├─ Reconstruct UI with match state
                ├─ Resume timer to 1:30 (90 seconds)
                ├─ Get cached speech: "The economy is..."
                ├─ Send SYNTHESIZE_CACHED_SPEECH to Gateway
                ├─ Gateway calls Deepgram TTS
                ├─ Frontend plays audio
                └─ User hears: "The economy is crucial for..." (no gap!)

T=8:05  AI speech replay complete
        Frontend: Timer shows 0:50 (50 seconds left)
        Match continues normally
```

---

## 8. Implementation Order (BACKEND FIRST)

### Phase 4: Backend
1. **state_schema.py** - Update fields (remove turn_expires_at, add match-based timing)
2. **state.py** - Update initialize_match() and add helper
3. **redis_consumer.py** - Update REJOIN_MATCH handler (accumulate offline time)
4. **state.py** - Create new state endpoint
5. **routes/__init__.py** - Register state router

### Phase 5: Gateway (after Phase 4 complete)
1. Add GET_MATCH_STATE handler
2. Add SYNTHESIZE_CACHED_SPEECH handler
3. Update message router

### Phase 6: Frontend (after Phase 5 complete)
1. Create useRejoinProtocol hook
2. Update useDebateTimer hook
3. Call hooks in match component

---

## 9. Testing Checklist

### Backend
- [ ] State schema validates with new fields
- [ ] initialize_match() sets match_duration_seconds correctly
- [ ] time_remaining_seconds property calculates correctly
- [ ] REJOIN_MATCH accumulates offline_duration
- [ ] GET /matches/{id}/state returns all required fields
- [ ] active_stream_buffer is sent in response

### Gateway
- [ ] GET_MATCH_STATE forwards to backend correctly
- [ ] SYNTHESIZE_CACHED_SPEECH calls Deepgram TTS
- [ ] Audio streams back to frontend

### Frontend
- [ ] Timer pauses on disconnect
- [ ] Timer resumes on rejoin with correct time
- [ ] Rejoin sends GET_MATCH_STATE
- [ ] TTS audio plays for cached buffer
- [ ] UI reconstructs correctly from state

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| User disconnects during different formats (AP vs BP) | match_duration_seconds calculated per format |
| Multiple rapid reconnects | Queue rejoin requests, process serially |
| Offline duration accumulates incorrectly | Unit test timer calculations |
| TTS synthesis too slow | Cache audio on first play, reuse on re-play |
| Timer drift between frontend/backend | Frontend timer is authoritative, backend validates |

---

## 11. Success Criteria

✅ **User disconnects mid-debate**
- Timer pauses visually on frontend
- Tokens accumulate in Redis
- Active AI continues generating

✅ **User reconnects after 10 minutes**
- Frontend fetches state via Gateway
- Timer shows correct remaining time (excluding offline period)
- UI reconstructs with all prior context
- Cached AI speech plays via TTS
- Match continues seamlessly

✅ **No breaking changes**
- All existing AP/BP match flows work
- Existing tournaments unaffected
- Backend event handlers work as before

