# Detailed Code Changes for FAANG Rejoin Implementation

## 1. State Schema Update
**File:** `src/schemas/state_schema.py`

**Current Issues:**
- Relative timer `time_remaining_seconds` is static (doesn't update on reconnect)
- No connection state tracking
- No AI generation status
- No token buffering for mid-stream rejoin

**Required Changes:**
```python
# BEFORE:
class LiveMatchState(BaseModel):
    match_id: str
    format_type: str = "AP"
    status : str="waiting"
    current_turn_index: int =0
    schedule : List[Turn]
    time_remaining_seconds : int =300
    transcript: List[dict]=[]

# AFTER:
from datetime import datetime
from typing import Literal

class LiveMatchState(BaseModel):
    # === Core ===
    match_id: str
    format_type: str = "AP"
    
    # === Status (Enhanced) ===
    status: Literal["WAITING", "IN_PROGRESS", "PAUSED", "COMPLETED", "ABANDONED"] = "WAITING"
    
    # === Turn Management ===
    current_turn_index: int = 0
    schedule: List[Turn]
    
    # === Timer: ABSOLUTE Timestamps (CRITICAL!) ===
    # Store expiration as Unix timestamp so reconnect can recalculate
    turn_expires_at: int = None  # Unix timestamp (int)
    
    # === Connection State (NEW) ===
    is_user_connected: bool = True
    last_connected_at: int = None  # Unix timestamp when user last connected
    
    # === AI Generation State (NEW) ===
    # Track if AI is mid-stream so rejoin user can get catch-up buffer
    ai_stream_status: Literal["IDLE", "STREAMING", "COMPLETED"] = "IDLE"
    active_stream_buffer: str = ""  # Tokens generated so far (for mid-stream rejoin)
    
    # === Data ===
    transcript: List[dict] = []
    
    @property
    def time_remaining_seconds(self) -> int:
        """
        Calculate remaining time from absolute timestamp.
        
        This is critical for reconnection: if user rejoins after 2 mins,
        this property automatically returns 298 seconds (relative to NOW).
        
        Never use static timers like setInterval - always calculate from
        absolute turn_expires_at.
        """
        if not self.turn_expires_at:
            return 300  # Default 5 minutes
        
        now = int(datetime.utcnow().timestamp())
        remaining = self.turn_expires_at - now
        return max(0, remaining)  # Never negative
```

---

## 2. State Manager Updates
**File:** `src/engine/state.py`

**Current Issues:**
- `initialize_match()` doesn't set `turn_expires_at`
- No timestamp management for reconnect
- Missing connection state initialization

**Required Changes:**

### Change 1: Update `initialize_match()`
```python
# BEFORE:
async def initialize_match(self, match_id: str, human_side: str, format_type: str, preferred_role: str = None) -> LiveMatchState:
    """Creates a initial game state and save it to Redis."""
    await self._ensure_connection()
    full_schedule = self._generate_schedule(format_type, human_side, preferred_role)
    state = LiveMatchState(
        match_id=match_id,
        format_type=format_type,
        status="in_progress",
        current_turn_index=0,
        schedule=full_schedule
    )
    await self.update_state(state)
    return state

# AFTER:
async def initialize_match(self, match_id: str, human_side: str, format_type: str, preferred_role: str = None) -> LiveMatchState:
    """Creates initial game state and save it to Redis."""
    await self._ensure_connection()
    from datetime import datetime
    
    full_schedule = self._generate_schedule(format_type, human_side, preferred_role)
    
    # CRITICAL: Set absolute timestamps for reconnect safety
    now = int(datetime.utcnow().timestamp())
    
    state = LiveMatchState(
        match_id=match_id,
        format_type=format_type,
        status="IN_PROGRESS",  # Changed from "in_progress"
        current_turn_index=0,
        schedule=full_schedule,
        turn_expires_at=now + 300,  # 5 minutes from now (absolute, not relative)
        is_user_connected=True,  # NEW: User starts connected
        last_connected_at=now,   # NEW: Track connection timestamp
        ai_stream_status="IDLE",  # NEW: No AI streaming yet
        active_stream_buffer="",  # NEW: Empty buffer
    )
    await self.update_state(state)
    return state
```

---

## 3. AI Response Generator (Token Buffering)
**File:** `src/workers/ai_response_generator.py`

**Current Issues:**
- Tokens stream to Redis Pub/Sub but are NOT buffered
- If user reconnects mid-stream, they miss first half of speech
- No `ai_stream_status` tracking

**Required Changes:**

### Change 1: Add streaming callback with buffering
```python
# Find this line in generate_ai_response():
response = await debater.orchestrate_debater_response(
    transcript=transcript,
    motion=motion_text,
    speaker_role=speaker_role,  
    speaker_id=speaker_id,
    speaker_side=speaker_side,
    difficulty_level=skill_level,
    personality_trait="balanced",
    session_id=match_id,
    channel=channel
)

# CHANGE TO:
# Mark AI as streaming
state.ai_stream_status = "STREAMING"
state.active_stream_buffer = ""
await state_manager.update_state(state)
logger.info(f"[AI] Marked match {match_id} as STREAMING")

# Create streaming callback that buffers tokens
async def stream_callback(token: str):
    """Called on each token from LLM"""
    # Append to Redis temporary buffer for mid-stream rejoin
    await client.append(f"match:{match_id}:active_stream", token)
    
    # Update state buffer in-memory (will be persisted after generation)
    state.active_stream_buffer += token
    
    # Publish to Redis Pub/Sub for live WebSocket stream
    await client.publish(channel, json.dumps({
        "event": "AI_TOKEN",
        "token": token,
        "cumulative_length": len(state.active_stream_buffer)
    }))

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
    stream_callback=stream_callback  # NEW: Pass streaming callback
)

# After response complete, update status
state.ai_stream_status = "COMPLETED"
await state_manager.update_state(state)

# Delete temporary Redis buffer (user should have received full speech by now)
await client.delete(f"match:{match_id}:active_stream")
logger.info(f"[AI] Cleaned up active stream buffer for match {match_id}")
```

---

## 4. Redis Consumer (Disconnect/Rejoin Handling)
**File:** `src/workers/redis_consumer.py`

**Current Issues:**
- Only handles START_MATCH (assumes fresh start)
- No REJOIN handling (mid-session reconnect)
- No DISCONNECT handling (pause user timer)
- No mid-stream rejoin buffer sending

**Required Changes:**

### Change 1: Add REJOIN_MATCH event handler
```python
# After the START_MATCH handler (around line 150), ADD:

                # EVENT: REJOIN_MATCH - User reconnecting after disconnect
                elif action == "REJOIN_MATCH":
                    logger.info(
                        f"[CONSUMER] User REJOIN for match {match_id}. "
                        f"Validating state..."
                    )
                    state = await state_manager.get_state(match_id)
                    
                    # Safety: Is match still valid?
                    if not state or state.status in ["COMPLETED", "ABANDONED"]:
                        logger.warning(
                            f"[CONSUMER] Cannot rejoin match {match_id}: "
                            f"status is {state.status if state else 'None'}"
                        )
                        await client.publish(channel, json.dumps({
                            "event": "REJOIN_FAILED",
                            "reason": "Match not in progress"
                        }))
                        continue
                    
                    # Get rejoin timestamp from event
                    last_turn_index = data.get("last_turn_index", state.current_turn_index)
                    user_timestamp = data.get("timestamp")
                    
                    # Check for race condition: Did turns advance while user was offline?
                    if last_turn_index != state.current_turn_index:
                        logger.warning(
                            f"[CONSUMER] Race condition detected in match {match_id}: "
                            f"User thought turn was {last_turn_index}, "
                            f"but current is {state.current_turn_index}"
                        )
                        # Send STATE_SYNC to bring frontend up to date
                        await client.publish(channel, json.dumps({
                            "event": "STATE_SYNC",
                            "current_turn_index": state.current_turn_index,
                            "current_speaker_role": state.schedule[state.current_turn_index].role,
                            "current_speaker_side": state.schedule[state.current_turn_index].side,
                            "transcript": state.transcript
                        }))
                    
                    # Mark user as reconnected
                    from datetime import datetime
                    state.is_user_connected = True
                    state.last_connected_at = int(datetime.utcnow().timestamp())
                    await state_manager.update_state(state)
                    logger.info(f"[CONSUMER] Marked user as connected for match {match_id}")
                    
                    # Get current speaker
                    current_speaker = state.schedule[state.current_turn_index]
                    
                    # CRITICAL: If AI is mid-stream, send catch-up buffer
                    if state.ai_stream_status == "STREAMING" and state.active_stream_buffer:
                        logger.info(
                            f"[CONSUMER] Sending {len(state.active_stream_buffer)} char "
                            f"catch-up buffer to rejoining user"
                        )
                        await client.publish(channel, json.dumps({
                            "event": "CATCH_UP_BUFFER",
                            "text": state.active_stream_buffer,
                            "is_complete": False,
                            "speaker_role": current_speaker.role
                        }))
                        # Continue to resume streaming below
                    
                    # Resume appropriate speaker
                    if current_speaker.player_type == "ai":
                        if state.ai_stream_status == "IDLE":
                            # Start new AI turn
                            logger.info(
                                f"[CONSUMER] Starting AI turn for {current_speaker.role} "
                                f"on rejoin"
                            )
                            cancel_active_task(match_id)
                            active_tasks[match_id] = asyncio.create_task(
                                generate_ai_response(
                                    client=client,
                                    channel=channel,
                                    match_id=match_id,
                                    state=state
                                )
                            )
                        elif state.ai_stream_status == "STREAMING":
                            logger.info(
                                f"[CONSUMER] AI still streaming for {current_speaker.role}, "
                                f"user will rejoin mid-stream"
                            )
                            # AI is still generating, don't start new task
                        else:  # COMPLETED
                            logger.info(
                                f"[CONSUMER] AI speech already complete for "
                                f"{current_speaker.role}, notifying frontend"
                            )
                            await client.publish(channel, json.dumps({
                                "event": "AI_SPEECH_COMPLETE",
                                "speaker_role": current_speaker.role,
                                "speech": state.transcript[-1]["content"] if state.transcript else ""
                            }))
                    else:
                        # Human's turn
                        logger.info(
                            f"[CONSUMER] Resuming human turn for {current_speaker.role} "
                            f"on rejoin"
                        )
                        await client.publish(channel, json.dumps({
                            "event": "TURN_STARTED",
                            "speaker": "human",
                            "role": current_speaker.role,
                            "side": current_speaker.side,
                            "turn_index": state.current_turn_index,
                            "time_remaining": state.time_remaining_seconds  # Calculated from absolute timestamp
                        }))
```

### Change 2: Add DISCONNECT event handler
```python
# After the REJOIN handler, ADD:

                # EVENT: DISCONNECT - User lost WebSocket connection
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
                    from datetime import datetime
                    state.last_connected_at = int(datetime.utcnow().timestamp())
                    
                    # Get current speaker
                    current_speaker = state.schedule[state.current_turn_index]
                    
                    # If user was speaking, pause the turn (timer pauses)
                    if current_speaker.player_type == "human":
                        state.status = "PAUSED"
                        logger.info(
                            f"[CONSUMER] Paused human turn for {current_speaker.role} "
                            f"in match {match_id} due to disconnect"
                        )
                    
                    # If AI was speaking, DO NOTHING
                    # Let Python continue generating, tokens go to void
                    # User will get catch-up buffer on rejoin
                    
                    await state_manager.update_state(state)
                    logger.info(f"[CONSUMER] Updated state for disconnect in match {match_id}")
```

---

## 5. API Endpoint for State Hydration
**File:** `src/api/routes/v1/{format}/matches.py` (both AP and BP)

**Current Status:** No such endpoint exists

**Required:** Add GET `/matches/{match_id}/state` for rejoin hydration

```python
# Add this new endpoint to the router:

from src.schemas.state_schema import LiveMatchState
from src.engine.state import state_manager
from src.core.database import SessionLocal
from src.repositories.ap.matches import APMatchRepository
from src.repositories.bp.matches import BPMatchRepository

@router.get(
    "/{match_id}/state",
    response_model=APIResponse[dict],
    summary="Get match state for rejoin hydration",
    tags=["Matches - Rejoin"]
)
async def get_match_state_for_rejoin(
    match_id: str = Path(..., description="Match UUID"),
    user: CurrentUserData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get full match state for rejoin hydration.
    
    Called by frontend BEFORE establishing WebSocket reconnection.
    Provides:
    - Complete transcript of all completed speeches
    - Current turn index and speaker
    - Time remaining (calculated from absolute timestamp)
    - AI stream status and buffer (for mid-stream rejoin)
    - Match status
    
    Used to restore frontend state when user reconnects after disconnect.
    
    Response (200 OK):
    {
        "match_id": "uuid",
        "status": "IN_PROGRESS",
        "current_turn_index": 3,
        "current_speaker": {
            "role": "Deputy Prime Minister",
            "side": "Government",
            "player_type": "ai"
        },
        "transcript": [...],
        "time_remaining_seconds": 142,
        "is_user_connected": false,
        "ai_stream_status": "STREAMING",
        "active_stream_buffer": "The economy is..."
    }
    """
    try:
        # Step 1: Get match from database (verify permissions)
        match_repo = APMatchRepository
        match_data = match_repo.get_match_with_motion(db, match_id)
        if not match_data:
            match_repo = BPMatchRepository
            match_data = match_repo.get_match_with_motion(db, match_id)
        
        if not match_data:
            raise HTTPException(status_code=404, detail="Match not found")
        
        debate_session = match_data[0]
        
        # Step 2: Check authorization (user owns this match)
        if debate_session.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this match"
            )
        
        # Step 3: Get Redis state
        state = await state_manager.get_state(match_id)
        if not state:
            # Match existed but Redis state lost (shouldn't happen)
            raise HTTPException(
                status_code=500,
                detail="Match state not found in cache"
            )
        
        # Step 4: Build hydration payload
        current_speaker = state.schedule[state.current_turn_index]
        
        return APIResponse(
            data={
                "match_id": state.match_id,
                "status": state.status,
                "current_turn_index": state.current_turn_index,
                "current_speaker": {
                    "role": current_speaker.role,
                    "side": current_speaker.side,
                    "player_type": current_speaker.player_type
                },
                "transcript": state.transcript,
                "time_remaining_seconds": state.time_remaining_seconds,  # Calculated from absolute timestamp
                "is_user_connected": state.is_user_connected,
                "ai_stream_status": state.ai_stream_status,
                "active_stream_buffer": state.active_stream_buffer,
                "turn_expires_at": state.turn_expires_at  # For debugging
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching match state for rejoin: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch match state"
        )
```

---

## 6. Frontend Rejoin Implementation
**File:** `agora-frontend/Agora-Frontend/src/store/arenaStore.ts`

**Current Issues:**
- Simple `connect()` doesn't hydrate state before WebSocket
- No catch-up buffer handling for mid-stream rejoin
- No state sync on race conditions

**Required Changes:**

### Change 1: Add hydration method
```typescript
// Add this new method to arenaStore:

const hydrateMatchState = async (matchId: string, token: string) => {
  try {
    const response = await fetch(
      `/api/v1/matches/${matchId}/state`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Match not found');
      }
      throw new Error(`Failed to hydrate: ${response.statusText}`);
    }
    
    const { data } = await response.json();
    
    // Restore state from hydration payload
    set({
      transcript: data.transcript,
      currentSpeaker: data.current_speaker,
      currentTurnIndex: data.current_turn_index,
      timeRemaining: data.time_remaining_seconds,
      aiBufferedText: data.active_stream_buffer,
      aiStreamStatus: data.ai_stream_status,
      isUserConnected: data.is_user_connected
    });
    
    logger.info(`Hydrated state for match ${matchId}`);
    return true;
  } catch (error) {
    logger.error('Failed to hydrate match state:', error);
    throw error;
  }
};
```

### Change 2: Update connect() to support REJOIN
```typescript
// BEFORE:
const connect = async (matchId: string, token: string) => {
  try {
    const wsUrl = `${WS_BASE_URL}/ws/live?match_id=${matchId}&token=${token}`;
    socket = new WebSocket(wsUrl);
    // ...
  } catch (error) {
    // ...
  }
};

// AFTER:
const connect = async (matchId: string, token: string, isRejoin: boolean = false) => {
  try {
    // STEP 1: If rejoin, hydrate state BEFORE WebSocket
    if (isRejoin) {
      logger.info(`Rejoining match ${matchId}, hydrating state...`);
      await hydrateMatchState(matchId, token);
    }
    
    // STEP 2: Establish WebSocket
    const wsUrl = `${WS_BASE_URL}/ws/live?match_id=${matchId}&token=${token}`;
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
      logger.info(`WebSocket connected for match ${matchId}`);
      
      // Send appropriate action
      if (isRejoin) {
        // Tell backend this is a rejoin (not fresh START_MATCH)
        socket.send(JSON.stringify({
          action: "REJOIN_MATCH",
          match_id: matchId,
          last_turn_index: get().currentTurnIndex,
          timestamp: Date.now()
        }));
        logger.info('Sent REJOIN_MATCH action to backend');
      } else {
        // Fresh start
        socket.send(JSON.stringify({
          action: "START_MATCH"
        }));
      }
    };
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // NEW: Handle catch-up buffer for mid-stream rejoin
      if (data.event === "CATCH_UP_BUFFER") {
        logger.info(`Received catch-up buffer (${data.text.length} chars)`);
        set({
          aiBufferedText: data.text,
          aiStreamStatus: data.is_complete ? "COMPLETED" : "STREAMING"
        });
        return;
      }
      
      // NEW: Handle race condition (state changed while offline)
      if (data.event === "STATE_SYNC") {
        logger.warn('Race condition detected, syncing state from backend');
        set({
          currentTurnIndex: data.current_turn_index,
          currentSpeaker: {
            role: data.current_speaker_role,
            side: data.current_speaker_side,
            player_type: 'ai' // Infer from backend
          },
          transcript: data.transcript
        });
        return;
      }
      
      // ... existing message handlers ...
    };
    
    // ... rest of connect logic ...
  } catch (error) {
    // ...
  }
};
```

### Change 3: Update rejoin button in history page
```typescript
// File: agora-frontend/Agora-Frontend/src/app/history/page.tsx
// OLD:
<Link href={`/debate/${match.id}?format=${match.format || 'ap'}`}>
  Rejoin Arena
</Link>

// NEW:
const handleRejoinClick = async () => {
  try {
    // Use flag to signal rejoin (vs fresh start)
    await connect(match.id, token, true);  // isRejoin = true
    router.push(`/debate/${match.id}?format=${match.format || 'ap'}`);
  } catch (error) {
    showError('Failed to rejoin match. Try again.');
  }
};

<Button onClick={handleRejoinClick}>
  Rejoin Arena
</Button>
```

---

## 7. Heartbeat + Timeout (Optional but Recommended)

### Frontend: Keep-alive heartbeat
**File:** `agora-frontend/Agora-Frontend/src/store/arenaStore.ts`

```typescript
let heartbeatInterval: NodeJS.Timeout | null = null;

const setupHeartbeat = (matchId: string, token: string) => {
  // Clear existing heartbeat
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
  }
  
  heartbeatInterval = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      // Send heartbeat
      socket.send(JSON.stringify({ action: "HEARTBEAT" }));
    } else if (socket && socket.readyState === WebSocket.CLOSED) {
      // Connection died, attempt auto-rejoin
      logger.warn('WebSocket died, attempting auto-rejoin...');
      clearInterval(heartbeatInterval);
      connect(matchId, token, true);  // isRejoin = true
    }
  }, 30000); // Every 30 seconds
};

// Call in connect() onopen handler:
socket.onopen = () => {
  setupHeartbeat(matchId, token);
  // ... send action ...
};
```

### Backend: Timeout cleanup
**File:** `src/workers/redis_consumer.py`

```python
import asyncio
from datetime import datetime, timedelta

# Track session timeouts
session_timeouts = {}
SESSION_TIMEOUT_SECONDS = 1800  # 30 minutes

async def start_inactivity_timeout(match_id: str, client: redis.Redis):
    """Start inactivity timeout for a session"""
    if match_id in session_timeouts:
        session_timeouts[match_id].cancel()
    
    async def timeout_callback():
        logger.warning(
            f"[TIMEOUT] Match {match_id} inactive for 30 minutes, "
            f"marking as abandoned"
        )
        state = await state_manager.get_state(match_id)
        if state:
            state.status = "ABANDONED"
            await state_manager.update_state(state)
        
        # Cancel any pending AI task
        if match_id in active_tasks:
            active_tasks[match_id].cancel()
            del active_tasks[match_id]
        
        del session_timeouts[match_id]
    
    timeout_handle = asyncio.create_task(
        asyncio.sleep(SESSION_TIMEOUT_SECONDS)
    )
    session_timeouts[match_id] = timeout_handle
    
    try:
        await timeout_handle
        await timeout_callback()
    except asyncio.CancelledError:
        logger.debug(f"[TIMEOUT] Reset timeout for match {match_id}")

# In START_MATCH handler, after marking user connected:
await start_inactivity_timeout(match_id, client)

# In REJOIN_MATCH handler:
# Reset the timeout
if match_id in session_timeouts:
    session_timeouts[match_id].cancel()
await start_inactivity_timeout(match_id, client)
```

---

## Summary: Files to Modify

| Priority | File | Changes | Complexity |
|----------|------|---------|-----------|
| 🔴 HIGH | `src/schemas/state_schema.py` | Add 5 fields + property | Easy |
| 🔴 HIGH | `src/engine/state.py` | Set timestamps on init | Easy |
| 🔴 HIGH | `src/workers/redis_consumer.py` | Add REJOIN/DISCONNECT handlers | Hard |
| 🟡 MEDIUM | `src/workers/ai_response_generator.py` | Add streaming callback + buffering | Medium |
| 🟡 MEDIUM | `src/api/routes/v1/ap/matches.py` | Add `/state` endpoint | Easy |
| 🟡 MEDIUM | `src/api/routes/v1/bp/matches.py` | Add `/state` endpoint (same code) | Easy |
| 🟡 MEDIUM | Frontend `arenaStore.ts` | Add hydration + rejoin logic | Medium |
| 🟢 LOW | Frontend components | Update rejoin button | Easy |

**Total Effort: ~18 hours for production-grade implementation**
