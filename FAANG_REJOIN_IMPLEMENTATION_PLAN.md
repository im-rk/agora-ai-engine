# FAANG-Level Rejoin Match Implementation Plan

## Executive Summary

**Current Status: D-**
Your implementation has the **foundation** (Redis persistence) but **missing critical FAANG patterns**:
- ❌ No `is_user_connected` state tracking
- ❌ No `turn_expires_at` (absolute timestamps)
- ❌ No `ai_stream_status` 
- ❌ No token buffering for mid-stream rejoin
- ❌ No `/api/matches/{id}/state` hydration endpoint
- ❌ No disconnect → pause timer logic
- ❌ No Rejoin event handler (START_MATCH always rebuilds)

**Production Gap: ~3-5 days of work** for comprehensive fix

---

## Part 1: What FAANG Pattern Requires

### Single Source of Truth: Redis Match State Hash

**Current (Broken):**
```python
# src/schemas/state_schema.py
class LiveMatchState(BaseModel):
    match_id: str
    format_type: str = "AP"
    status: str = "waiting"
    current_turn_index: int = 0
    schedule: List[Turn]
    time_remaining_seconds: int = 300
    transcript: List[dict] = []
    # ❌ Missing: is_user_connected, turn_expires_at, ai_stream_status
```

**Required (FAANG Standard):**
```python
class LiveMatchState(BaseModel):
    # Core IDs
    match_id: str
    format_type: str
    
    # Status tracking
    status: str  # "IN_PROGRESS", "PAUSED", "COMPLETED", "ABANDONED"
    
    # Turn management
    current_turn_index: int
    schedule: List[Turn]
    
    # Timer: ABSOLUTE Unix timestamp, not relative
    turn_expires_at: int  # Unix timestamp when turn expires
    time_remaining_seconds: int  # Calculated as (turn_expires_at - now())
    
    # Connection state
    is_user_connected: bool  # ✅ NEW: User is online on WebSocket
    last_connected_at: int  # Unix timestamp
    
    # AI generation state
    ai_stream_status: str  # "IDLE", "STREAMING", "COMPLETED"
    active_stream_buffer: str  # ✅ NEW: Cached tokens from in-progress generation
    
    # Data persistence
    transcript: List[dict]
```

---

## Part 1B: The HYBRID Approach (Optimal Strategy)

### **Why Full Generation is Better Than Pause & Resume**

After analyzing your requirements, we've identified the **HYBRID approach** which is superior:

```
User Disconnects While AI Speaking:

❌ OLD (Pause approach):
  - Cancel AI task
  - Save partial buffer
  - Wait for user rejoin
  - Resume AI from context (risky, expensive)
  
✅ NEW (Full Generation - HYBRID):
  - Let AI keep generating (one cheap LLM call)
  - Cache full speech in Redis
  - User disconnected: tokens → Pub/Sub → Redis cache (not WebSocket)
  - User reconnects: send full cached speech instantly
```

### **Cost Analysis**

| Metric | Pause & Resume | Full Generation | Winner |
|--------|---|---|---|
| **LLM Cost** | $0.002 (start + restart) | $0.001 (single call) | ✅ Full Gen |
| **Restart Overhead** | High (rebuild context) | None | ✅ Full Gen |
| **User Latency** | Moderate (resume typing) | Instant (full speech) | ✅ Full Gen |
| **Code Complexity** | Hard (context management) | Simple (cache full) | ✅ Full Gen |
| **Error Rate** | Higher (LLM resume fails) | Lower (already complete) | ✅ Full Gen |

### **Architecture Flow (Full Generation)**

```
Timeline: User disconnects at T=3:00 while AI speaking PM

T=0:00  ┌─ AI starts generating
        ├─ ai_stream_status = "STREAMING"
        ├─ active_stream_buffer = ""
        └─ Each token: → Redis Pub/Sub → Gateway → WebSocket → Frontend

T=0:30  ├─ Generated: "The economy is crucial..."
        ├─ active_stream_buffer = "The economy is crucial..."
        ├─ Frontend displays live ✅
        └─ Redis cached in state

T=3:00  │ USER DISCONNECTS ⚠️
        ├─ WebSocket closes
        ├─ Gateway stops forwarding to user
        ├─ ❌ Frontend loses connection
        └─ ✅ Redis Pub/Sub KEEPS flowing

T=3:00-5:00 │ OFFLINE PERIOD (AI still generating)
        ├─ "...crucial for growth..."
        ├─ "...and fiscal stability..."
        ├─ "...ensuring economic prosperity"
        ├─ active_stream_buffer = full PM speech (700+ chars)
        ├─ ✅ NO WASTED COMPUTE (single LLM call)
        ├─ ✅ State persisted in Redis every token
        └─ ✅ Full speech cached and ready

T=5:00  │ AI FINISHES PM SPEECH
        ├─ ai_stream_status = "COMPLETED"
        ├─ active_stream_buffer = full speech ✅
        └─ Redis has complete cached speech

T=8:00  │ USER RECONNECTS 🔌
        ├─ Frontend: REST call GET /api/matches/{id}/state
        ├─ Backend: Reads Redis state
        ├─ Sends: {"event": "CATCH_UP_BUFFER", "text": "The economy is crucial..."}
        ├─ Frontend: Renders ENTIRE speech instantly ✅
        ├─ No typing animation, but complete context
        ├─ Then continues to next speaker (LO)
        └─ Perfect seamless experience! 🎉
```

### **Why This Works**

1. **Single LLM Call**: One API call to Groq, full speech generation (cheap)
2. **Network Efficient**: Tokens still stream to Redis (nobody listening on WS is ok)
3. **Storage Cheap**: Full speech ~500-1000 chars, trivial Redis space
4. **UX Perfect**: User gets FULL context on rejoin, not partial resume
5. **Error Proof**: No "resume from context" complexity
6. **State Safe**: State already persisted in Redis via streaming

### **Implementation Change**

Instead of:
```python
# Cancel on disconnect
if action == "DISCONNECT":
    active_tasks[match_id].cancel()  # ❌ DON'T DO THIS
```

Just do:
```python
# Let AI finish, user marked offline
if action == "DISCONNECT":
    state.is_user_connected = False
    # AI task continues naturally
    # Tokens still stream to Redis cache
    # Don't cancel anything ✅
```

---

## Part 2: Phase-by-Phase Required Changes

### **PHASE 1: Data Model Updates**

#### File: `src/schemas/state_schema.py`
**Changes:**
1. Add 5 new fields to `LiveMatchState`
2. Change `time_remaining_seconds` from static to calculated property
3. Add constants for status enum

**Code:**
```python
from datetime import datetime
from typing import Literal

class LiveMatchState(BaseModel):
    # === Core ===
    match_id: str
    format_type: str = "AP"
    
    # === Status ===
    status: Literal["IN_PROGRESS", "PAUSED", "COMPLETED", "ABANDONED"] = "IN_PROGRESS"
    
    # === Turn Management ===
    current_turn_index: int = 0
    schedule: List[Turn]
    
    # === Timer: ABSOLUTE timestamps (CRITICAL!) ===
    turn_expires_at: int  # Unix timestamp when turn expires
    
    # === Connection State (NEW) ===
    is_user_connected: bool = True
    last_connected_at: int = None  # Unix timestamp
    
    # === AI Generation State (NEW) ===
    ai_stream_status: str = "IDLE"  # "IDLE", "STREAMING", "COMPLETED"
    active_stream_buffer: str = ""  # Buffered tokens from mid-stream generation
    
    # === Data ===
    transcript: List[dict] = []
    
    @property
    def time_remaining_seconds(self) -> int:
        """Calculate remaining time from absolute timestamp"""
        now = int(datetime.utcnow().timestamp())
        remaining = self.turn_expires_at - now
        return max(0, remaining)
```

#### File: `src/engine/state.py`
**Changes:**
1. Update `initialize_match()` to set `turn_expires_at` (now + 300 seconds)
2. Update `update_state()` to handle new fields
3. Add timestamp management

**Code locations to update:**
```python
async def initialize_match(self, match_id: str, human_side: str, format_type: str, ...):
    # Add:
    now = int(datetime.utcnow().timestamp())
    state.turn_expires_at = now + 300  # 5 minutes
    state.is_user_connected = True
    state.last_connected_at = now
    state.ai_stream_status = "IDLE"
    state.active_stream_buffer = ""
```

---

### **PHASE 2: Disconnect Handling (Smart, Not Cancellation)**

**Context:** When user's WebSocket drops, here's what happens:

```python
# When DISCONNECT event fires
if action == "DISCONNECT":
    state.is_user_connected = False  # Mark user offline
    state.status = "PAUSED"  # Only if HUMAN was speaking
    
    # CRITICAL: Do NOT cancel AI task!
    # Let it finish naturally (one cheap LLM call)
    # Tokens flow to Redis, cache the full speech
    
    # Current speaker check:
    current_speaker = state.schedule[state.current_turn_index]
    
    if current_speaker.player_type == "human":
        # User was speaking: pause timer
        state.status = "PAUSED"
        # turn_expires_at stays same
        # On rejoin, extend by offline duration
    
    else:  # AI was speaking
        # Do absolutely NOTHING
        # AI continues generating
        # Tokens → Redis Pub/Sub → Cache
        # User offline, doesn't matter
        # On rejoin: send full cached speech
    
    await state_manager.update_state(state)
```

**Key Insight:** You identified this correctly!
- ✅ Let AI finish (one LLM call = $0.001)
- ✅ Full speech cached in Redis
- ❌ Don't restart LLM (expensive, risky)
- ✅ User gets complete context on rejoin

---

### **PHASE 3: Token Buffering (Full Speech Caching)**

#### File: `src/workers/ai_response_generator.py`

**The Flow:**

```python
async def generate_ai_response(client, channel, match_id, state):
    """Generate AI response and cache full speech for rejoin recovery"""
    
    # Mark AI as streaming
    state.ai_stream_status = "STREAMING"
    state.active_stream_buffer = ""
    await state_manager.update_state(state)
    
    # Streaming callback: accumulate tokens in buffer
    async def stream_callback(token: str):
        """Called on EACH token from LLM"""
        # Accumulate in buffer
        state.active_stream_buffer += token
        
        # Update state in Redis (persists for rejoin)
        await state_manager.update_state(state)
        
        # Publish to Pub/Sub for live rendering
        # (if user is connected, they see it live)
        # (if user disconnected, nobody listens but it still gets cached)
        await client.publish(channel, json.dumps({
            "event": "AI_TOKEN",
            "token": token,
            "buffer_size": len(state.active_stream_buffer)
        }))
    
    # Generate response with streaming
    response = await debater.orchestrate_debater_response(
        transcript=transcript,
        motion=motion_text,
        speaker_role=speaker_role,
        speaker_id=speaker_id,
        speaker_side=speaker_side,
        difficulty_level=skill_level,
        personality_trait="balanced",
        session_id=match_id,
        channel=channel,
        stream_callback=stream_callback  # ✅ Pass callback
    )
    
    # Mark complete
    state.ai_stream_status = "COMPLETED"
    # active_stream_buffer already has full speech
    await state_manager.update_state(state)
    
    # No need to delete buffer - it's the full speech!
    # On rejoin, user gets this full speech via CATCH_UP_BUFFER event
    
    logger.info(
        f"[AI] Complete PM speech ({len(state.active_stream_buffer)} chars) "
        f"cached for rejoin recovery"
    )
    
    return response
```

**What Happens During User Disconnect:**

```
Timeline (User disconnects at T=3:00):

T=0:00  ai_stream_status = "STREAMING"
        active_stream_buffer = ""

T=0:30  Generated: "The economy is crucial..."
        active_stream_buffer = "The economy is crucial..."
        
        Pub/Sub event published
        ├─ User connected: WebSocket forwards to frontend ✅
        └─ User disconnected: nobody listens, but still cached ✅

T=3:00  USER DISCONNECTS
        ├─ WebSocket closes
        ├─ active_stream_buffer = "The economy is crucial..." (PERSISTED)
        ├─ ai_stream_status = "STREAMING" (PERSISTED)
        └─ Redis state saved with both fields ✅

T=3:00-5:00  AI keeps generating
        ├─ "...crucial for growth..."
        ├─ active_stream_buffer += "...crucial for growth..."
        ├─ Redis state updated each token
        ├─ Pub/Sub event published (nobody listening)
        └─ No error, no waste, just caching ✅

T=5:00  AI finishes
        ├─ ai_stream_status = "COMPLETED"
        ├─ active_stream_buffer = full 1000+ char speech ✅
        └─ Redis persisted completely ✅

T=8:00  USER REJOINS
        ├─ REST call: GET /api/matches/{id}/state
        ├─ Backend reads active_stream_buffer (full speech)
        ├─ Sends CATCH_UP_BUFFER event
        ├─ Frontend displays entire PM speech instantly ✅
        └─ Seamless experience, user sees full context!
```

---

### **PHASE 4: New REST Endpoint for Rejoin Hydration**

#### File: `src/api/routes/v1/{format}/matches.py`
**Add new endpoint:**

```python
@router.get(
    "/{match_id}/state",
    response_model=APIResponse[StateHydrationPayload],
    summary="Get match state for rejoin hydration"
)
async def get_match_state_for_rejoin(
    match_id: str = Path(...),
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get full match state for rejoin hydration (REST call BEFORE WebSocket).
    
    Used when user rejoins after disconnect.
    Provides:
    - Full transcript of completed speeches
    - Current turn index
    - Time remaining (calculated from absolute timestamp)
    - Current speaker role and side
    - Match status
    
    Response:
    {
      "match_id": "uuid",
      "status": "IN_PROGRESS",
      "current_turn_index": 3,
      "current_speaker_role": "Deputy Prime Minister",
      "current_speaker_side": "Government",
      "transcript": [...],
      "time_remaining_seconds": 142,
      "is_user_connected": false,
      "ai_stream_status": "IDLE"
    }
    """
    # Get Redis state
    state = await state_manager.get_state(match_id)
    if not state:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Check permissions (user owns this match)
    debate_session = await get_debate_session(db, match_id)
    if debate_session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Return hydration payload
    return APIResponse(
        data=StateHydrationPayload(
            match_id=state.match_id,
            status=state.status,
            current_turn_index=state.current_turn_index,
            current_speaker=state.schedule[state.current_turn_index],
            transcript=state.transcript,
            time_remaining_seconds=state.time_remaining_seconds,
            is_user_connected=state.is_user_connected,
            ai_stream_status=state.ai_stream_status,
            active_stream_buffer=state.active_stream_buffer,
        )
    )


@dataclass
class StateHydrationPayload:
    match_id: str
    status: str
    current_turn_index: int
    current_speaker: Turn
    transcript: List[dict]
    time_remaining_seconds: int
    is_user_connected: bool
    ai_stream_status: str
    active_stream_buffer: str
```

---

### **PHASE 5: Rejoin Event Handler in Redis Consumer**

#### File: `src/workers/redis_consumer.py`

**The Smart Rejoin Logic:**

```python
async def start_redis_consumer():
    async for message in pubsub.listen():
        # ... existing code ...
        
        # EVENT: REJOIN_MATCH - User reconnecting after disconnect
        elif action == "REJOIN_MATCH":
            logger.info(f"[CONSUMER] User REJOIN for match {match_id}")
            state = await state_manager.get_state(match_id)
            
            if not state or state.status in ["COMPLETED", "ABANDONED"]:
                await client.publish(channel, json.dumps({
                    "event": "REJOIN_FAILED",
                    "reason": "Match not in progress"
                }))
                continue
            
            # Extend turn deadline if user was offline
            # (only if they were the one speaking)
            current_speaker = state.schedule[state.current_turn_index]
            
            if current_speaker.player_type == "human" and state.status == "PAUSED":
                # User was speaking, timer was paused
                # Extend deadline by offline duration
                now = int(datetime.now(timezone.utc).timestamp())
                offline_duration = now - state.last_connected_at
                state.turn_expires_at += offline_duration
                logger.info(
                    f"[CONSUMER] Extended turn deadline by {offline_duration} secs "
                    f"for offline duration"
                )
            
            # Mark user as reconnected
            state.is_user_connected = True
            state.last_connected_at = int(datetime.now(timezone.utc).timestamp())
            state.status = "IN_PROGRESS"  # Resume from pause
            await state_manager.update_state(state)
            
            # Get current speaker
            current_speaker = state.schedule[state.current_turn_index]
            
            # CRITICAL: Send catch-up buffer if AI was generating
            if (current_speaker.player_type == "ai" and 
                state.ai_stream_status in ["STREAMING", "COMPLETED"] and 
                state.active_stream_buffer):
                
                logger.info(
                    f"[CONSUMER] Sending {len(state.active_stream_buffer)} char "
                    f"catch-up buffer to rejoining user"
                )
                
                # Send entire buffered speech at once
                await client.publish(channel, json.dumps({
                    "event": "CATCH_UP_BUFFER",
                    "text": state.active_stream_buffer,
                    "is_complete": (state.ai_stream_status == "COMPLETED"),
                    "speaker_role": current_speaker.role
                }))
                
                # If AI is still streaming, they'll get live tokens after this
                if state.ai_stream_status == "STREAMING":
                    logger.info(
                        f"[CONSUMER] AI still generating, live tokens will resume"
                    )
                elif state.ai_stream_status == "COMPLETED":
                    logger.info(
                        f"[CONSUMER] AI speech complete, proceeding to next speaker"
                    )
            
            # Resume or start next speaker
            if current_speaker.player_type == "ai" and state.ai_stream_status == "IDLE":
                # Fresh AI turn not started yet
                logger.info(
                    f"[CONSUMER] Starting AI turn for {current_speaker.role}"
                )
                cancel_active_task(match_id)
                active_tasks[match_id] = asyncio.create_task(
                    generate_ai_response(client, channel, match_id, state)
                )
            
            elif current_speaker.player_type == "human":
                # Human's turn
                logger.info(
                    f"[CONSUMER] Human turn for {current_speaker.role}, "
                    f"time remaining: {state.time_remaining_seconds} secs"
                )
                await client.publish(channel, json.dumps({
                    "event": "TURN_STARTED",
                    "speaker": "human",
                    "role": current_speaker.role,
                    "side": current_speaker.side,
                    "time_remaining": state.time_remaining_seconds
                }))
        
        # EVENT: DISCONNECT - User lost connection
        elif action == "DISCONNECT":
            logger.warning(
                f"[CONSUMER] User DISCONNECT from match {match_id}"
            )
            state = await state_manager.get_state(match_id)
            if not state:
                logger.warning(f"[CONSUMER] State not found for match {match_id}")
                continue
            
            # Mark user as offline
            state.is_user_connected = False
            state.last_connected_at = int(datetime.now(timezone.utc).timestamp())
            
            # Get current speaker
            current_speaker = state.schedule[state.current_turn_index]
            
            if current_speaker.player_type == "human":
                # User was speaking: pause the turn (timer pauses)
                state.status = "PAUSED"
                logger.info(
                    f"[CONSUMER] Paused human turn for {current_speaker.role} "
                    f"(time will extend on rejoin)"
                )
            else:
                # AI was speaking: do NOTHING, let it finish
                logger.info(
                    f"[CONSUMER] AI speaking, letting {current_speaker.role} "
                    f"finish naturally (one LLM call = cheap)"
                )
                # AI task continues
                # Tokens stream to Redis cache
                # User disconnected, doesn't matter
                # On rejoin: send full cached speech
            
            await state_manager.update_state(state)
```

**Key Differences from Original:**
- ✅ Don't cancel AI tasks - let them finish naturally
- ✅ Full speech accumulates in `active_stream_buffer`
- ✅ On rejoin, send complete speech via CATCH_UP_BUFFER
- ✅ AI continues generating even if user is offline
- ✅ Cheaper (one LLM call), simpler logic, better UX

---

### **PHASE 6: Frontend Rejoin Protocol**

#### File: `agora-frontend/src/app/[format]/[matchId]/page.tsx` or rejoin handler

**Current problem:**
```typescript
// Simple link navigation
<Link href={`/debate/${match.id}?format=${match.format || 'ap'}`}>
    Rejoin Arena
</Link>

// Immediately connects WebSocket without state recovery
useEffect(() => {
  connect(matchId, token)  // ❌ No hydration
}, [matchId, token])
```

**Required (FAANG Pattern):**
```typescript
async function rejoinMatch(matchId: string, token: string) {
  try {
    // STEP 1: Fetch hydration payload BEFORE WebSocket
    const response = await fetch(
      `/api/v1/matches/${matchId}/state`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    
    if (!response.ok) {
      if (response.status === 404) {
        router.push('/history'); // Match not found
        return;
      }
      throw new Error('Failed to fetch match state');
    }
    
    const { data: hydration } = await response.json();
    
    // STEP 2: Restore state from hydration payload
    store.setState({
      transcript: hydration.transcript,
      currentSpeakerRole: hydration.current_speaker.role,
      currentSpeakerSide: hydration.current_speaker.side,
      currentTurnIndex: hydration.current_turn_index,
      timeRemaining: hydration.time_remaining_seconds,
      aiStreamBuffer: hydration.active_stream_buffer,
    });
    
    // STEP 3: Now connect WebSocket with REJOIN action
    await connectWithRejoin(
      matchId,
      token,
      hydration.current_turn_index
    );
    
  } catch (error) {
    logger.error('Rejoin failed:', error);
    setError('Failed to rejoin match. Please try again.');
  }
}

async function connectWithRejoin(
  matchId: string,
  token: string,
  lastTurnIndex: number
) {
  const ws = new WebSocket(
    `${WS_BASE_URL}/ws/live?match_id=${matchId}&token=${token}`
  );
  
  ws.onopen = () => {
    // Send REJOIN action with state validation
    ws.send(JSON.stringify({
      action: "REJOIN_MATCH",
      match_id: matchId,
      last_turn_index: lastTurnIndex,
      timestamp: Date.now()
    }));
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // Handle mid-stream rejoin (catch-up buffer)
    if (data.event === "CATCH_UP_BUFFER") {
      store.setState({
        aiBufferedText: data.text,
        aiBufferComplete: data.is_complete
      });
      // Render buffered text immediately
      return;
    }
    
    // Race condition: state changed while offline
    if (data.event === "STATE_SYNC") {
      store.setState({
        currentTurnIndex: data.current_turn_index,
        currentSpeakerRole: data.current_speaker
      });
      return;
    }
    
    // Handle normal events as before
    // ...
  };
}

// Usage in component
<Button
  onClick={() => rejoinMatch(matchId, token)}
>
  Rejoin Arena
</Button>
```

---

### **PHASE 7: Heartbeat + Timeout Cleanup**

#### File: `src/workers/redis_consumer.py`

**Add timeout handler:**
```python
import asyncio

# Global timeout tracking
session_timeouts = {}  # { match_id: timeout_handle }
SESSION_TIMEOUT_SECONDS = 1800  # 30 minutes

async def start_session_timeout(match_id: str, client: redis.Redis):
    """Start timeout for inactive session"""
    if match_id in session_timeouts:
        session_timeouts[match_id].cancel()
    
    async def timeout_handler():
        await asyncio.sleep(SESSION_TIMEOUT_SECONDS)
        logger.warning(f"[TIMEOUT] Match {match_id} inactive for 30 mins")
        
        state = await state_manager.get_state(match_id)
        state.status = "ABANDONED"
        await state_manager.update_state(state)
        
        # Cancel any pending AI task
        if match_id in active_tasks:
            active_tasks[match_id].cancel()
        
        del session_timeouts[match_id]
    
    session_timeouts[match_id] = asyncio.create_task(timeout_handler())

async def reset_session_timeout(match_id: str):
    """Reset timeout on user activity"""
    if match_id in session_timeouts:
        session_timeouts[match_id].cancel()
    await start_session_timeout(match_id, ...)
```

#### File: Frontend heartbeat
```typescript
const setupHeartbeat = (matchId: string) => {
  const heartbeat = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "HEARTBEAT" }));
    } else {
      clearInterval(heartbeat);
      // Auto-rejoin on connection loss
      rejoinMatch(matchId, token);
    }
  }, 30000); // Every 30 seconds
};
```

---

## Part 3: Implementation Priority & Effort

| Phase | Component | Files | Hours | Difficulty |
|-------|-----------|-------|-------|------------|
| 1 | Data Model | `state_schema.py`, `state.py` | 2 | Easy |
| 2 | Disconnect Handling | Go Gateway (external) | 2 | Medium |
| 3 | Token Buffering | `ai_response_generator.py` | 3 | Medium |
| 4 | Hydration Endpoint | `matches.py` API routes | 2 | Easy |
| 5 | Rejoin Handler | `redis_consumer.py` | 4 | Hard |
| 6 | Frontend Protocol | `arenaStore.ts`, components | 3 | Medium |
| 7 | Heartbeat + Timeout | Both frontend + backend | 2 | Easy |
| **TOTAL** | **Full FAANG Rejoin** | **7 files** | **~18 hours** | **Hard** |

---

## Part 4: Testing Strategy

### Unit Tests
```python
# Test absolute timestamps don't break on reconnect
def test_rejoin_with_time_drift():
    # User reconnects 5 mins later
    # time_remaining_seconds should be 300 - 300 = 0
    # No hardcoded timer reset, purely calculated

# Test mid-stream rejoin
def test_catch_up_buffer_on_rejoin():
    # AI generates 500 chars
    # User rejoin → buffer sent → resume streaming
    # User sees all 500 chars + live stream

# Test race condition prevention
def test_no_dual_generation():
    # Start match → AI generating
    # User rejoins immediately → NO duplicate task
    # Only 1 task running
```

### Integration Tests
```python
# Full disconnect → rejoin flow
async def test_full_disconnect_rejoin_cycle():
    1. Start match
    2. AI begins speaking
    3. User disconnects
    4. User rejoins
    5. Verify transcript restored
    6. Verify stream continues (or completes)
```

---

## Summary: Why This Matters

| Problem | FAANG Solution | Your Benefit |
|---------|---|---|
| User loses WebSocket → loses entire debate | State in Redis survives disconnect | Zero data loss |
| AI keeps generating while user offline → wasted tokens | Mark AI status in Redis → check on rejoin | Save compute costs |
| User reconnects mid-speech → misses half the content | Buffer tokens in Redis → send on rejoin | Perfect UX |
| Connection drops silently → user confused | Heartbeat + explicit timeout | Clear error messaging |
| Race condition: dual WebSockets | Validate state on rejoin | Prevents state corruption |
| Relative timers break after reconnect | Absolute timestamps (Unix) | Correct time tracking |

**Bottom Line:** This is the difference between **MVP** (loses state on disconnect) and **Production Grade** (survives everything).
