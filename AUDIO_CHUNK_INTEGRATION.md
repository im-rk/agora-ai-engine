"""
AUDIO CHUNK CACHING - GATEWAY INTEGRATION GUIDE

This document explains how the Gateway should integrate with the
backend's audio chunk management system for smart audio resume on rejoin.

=============================================================================
OVERVIEW
=============================================================================

When a user reconnects after disconnecting during speech playback:
1. Backend sends CATCH_UP_BUFFER with undelivered chunks list
2. Gateway only sends audio chunks that haven't been sent yet
3. Frontend resumes from exact playback position (no full replay)

=============================================================================
ARCHITECTURE
=============================================================================

Backend Flow:
  AI Generation         → Cache text in Redis
  Synthesis Start       → Record synthesis_start_time
  Synthesis Complete    → Record synthesis_end_time
  User Disconnects      → Note chunks_last_sent_at

Gateway Flow:
  TTS Synthesis         → Create audio chunks
  Store Metadata        → Call chunk_manager.store_chunk_metadata()
  Audio Streaming       → Send chunks to frontend
  Track Delivery        → Call chunk_manager.mark_chunks_delivered()

Frontend Flow:
  Disconnect            → Lose audio stream connection
  Rejoin                → GET /api/v1/matches/{match_id}/state
  Parse Metadata        → Use synthesis_metadata + undelivered_chunks
  Resume Playback       → Play from estimated_playback_seconds

=============================================================================
GATEWAY INTEGRATION STEPS
=============================================================================

### STEP 1: Listen to CATCH_UP_BUFFER Event

When REJOIN_MATCH happens, Backend publishes:

```json
{
  "event": "CATCH_UP_BUFFER",
  "text": "The economy is crucial for debate because... [entire speech]",
  "is_complete": true,
  "speaker_role": "Prime Minister",
  "synthesis_metadata": {
    "synthesis_start_time": 1715340000,
    "synthesis_end_time": 1715340010,
    "estimated_playback_seconds": 25,
    "chunks_last_sent_at": 1715340005
  },
  "undelivered_chunks": [
    {
      "chunk_index": 3,
      "chunk_number": 3,
      "byte_start": 8192,
      "byte_end": 12288,
      "duration_ms": 5000,
      "synthesized_at": 1715340006
    },
    {
      "chunk_index": 4,
      "chunk_number": 4,
      "byte_start": 12288,
      "byte_end": 16384,
      "duration_ms": 5000,
      "synthesized_at": 1715340007
    }
  ]
}
```

### STEP 2: Call TTS Synthesis (if not cached)

```go
// Pseudo-code for Go Gateway handler
func handleCatchUpBuffer(event map[string]interface{}) {
    text := event["text"].(string)
    metadata := event["synthesis_metadata"].(map[string]interface{})
    
    // Check if audio is already cached for this speaker
    audioBytes, cached := getAudioFromCache(matchId, turnIndex)
    
    if !cached {
        // Call Deepgram TTS with chunk callback
        audioBytes = deepgramTTS.TextToSpeech(
            text,
            currentVoiceID,
            onChunkSynthesized  // Callback for each chunk
        )
        
        // Cache the complete audio
        cacheAudio(matchId, turnIndex, audioBytes)
    }
    
    // Send undelivered chunks only
    undeliveredChunks := event["undelivered_chunks"].([]map[string]interface{})
    sendAudioChunksToFrontend(undeliveredChunks, audioBytes, metadata)
}
```

### STEP 3: Store Chunk Metadata During Synthesis

As Deepgram TTS synthesizes audio, call the chunk manager:

```go
// When each chunk is synthesized
import "sync/http"

func onChunkSynthesized(chunkIndex int, audioBytes []byte, durationMs int) {
    // Calculate byte offsets
    byteStart := calculateByteStart(chunkIndex)  // e.g., 0, 4096, 8192
    byteEnd := byteStart + len(audioBytes)
    
    // Send to backend to store metadata
    chunkMetadata := map[string]interface{}{
        "chunk_index": chunkIndex,
        "chunk_number": chunkIndex,  // Sequential number during synthesis
        "byte_start": byteStart,
        "byte_end": byteEnd,
        "duration_ms": durationMs,
        "synthesized_at": time.Now().Unix(),
        "text_segment": extractTextSegment(chunkIndex),  // Optional
    }
    
    // Call backend API to store metadata
    // POST /api/v1/matches/{match_id}/chunks
    storeChunkMetadata(matchId, turnIndex, chunkMetadata)
}
```

### STEP 4: Send Only Undelivered Chunks to Frontend

```go
func sendAudioChunksToFrontend(
    undeliveredChunks []map[string]interface{},
    audioBytes []byte,
    metadata map[string]interface{},
) {
    synthMetadata := metadata["synthesis_metadata"].(map[string]interface{})
    estimatedPlaybackSeconds := synthMetadata["estimated_playback_seconds"].(int)
    
    for _, chunk := range undeliveredChunks {
        byteStart := chunk["byte_start"].(int)
        byteEnd := chunk["byte_end"].(int)
        
        // Extract only this chunk's audio
        chunkAudio := audioBytes[byteStart:byteEnd]
        
        // Send via WebSocket
        conn.WriteMessage(websocket.BinaryMessage, chunkAudio)
        
        // Send metadata so frontend knows playback position
        conn.WriteMessage(websocket.TextMessage, json.Marshal(map[string]interface{}{
            "event": "AUDIO_CHUNK",
            "chunk_number": chunk["chunk_number"],
            "playback_resume_seconds": estimatedPlaybackSeconds,
            "is_final": false,
        }))
    }
    
    // Signal completion
    conn.WriteMessage(websocket.TextMessage, json.Marshal(map[string]interface{}{
        "event": "AUDIO_COMPLETE",
        "speaker_role": speakerRole,
        "is_final": true,
    }))
}
```

### STEP 5: Mark Chunks as Delivered

After all chunks are sent successfully:

```go
func markChunksDelivered(matchId string) {
    // POST to backend
    resp, err := http.Post(
        fmt.Sprintf("http://localhost:8000/api/v1/matches/%s/chunks/delivered", matchId),
        "application/json",
        bytes.NewBufferString(fmt.Sprintf(`{"delivered_at": %d}`, time.Now().Unix())),
    )
    
    if err == nil && resp.StatusCode == 200 {
        logger.Info("Chunks marked as delivered for " + matchId)
    }
}
```

=============================================================================
STATE FLOW DURING REJOIN
=============================================================================

Timeline: PM speaking at 25 seconds when user disconnects

1. **T=25s (Disconnect)**
   - Backend state: 
     - `ai_stream_status`: "STREAMING" or "COMPLETED"
     - `synthesis_start_time`: 1715340000
     - `chunks_last_sent_at`: 1715340005 (5 seconds of audio sent)
     - `estimated_playback_seconds`: 25 (approx where they stopped)

2. **T=26s-30s (User Offline)**
   - AI continues generating text
   - Gateway continues synthesizing audio chunks 4, 5, 6
   - Chunks 4+ stored with `synthesized_at` > 1715340005

3. **T=31s (User Rejoin)**
   - GET /api/v1/matches/{match_id}/state returns:
     ```json
     {
       "synthesis_metadata": {
         "chunks_last_sent_at": 1715340005,
         "estimated_playback_seconds": 25
       },
       "undelivered_chunks": [
         {chunk 4, synthesized_at: 1715340006},
         {chunk 5, synthesized_at: 1715340007},
         {chunk 6, synthesized_at: 1715340008}
       ]
     }
     ```
   
   - CATCH_UP_BUFFER published with undelivered chunks
   
   - Gateway receives and sends ONLY chunks 4, 5, 6
   
   - Frontend receives and resumes from 25-second position
   
   - No full audio replay! ✅

=============================================================================
OPTIONAL: FRONTEND CHUNK STORAGE
=============================================================================

Frontend can also cache audio chunks locally for offline resilience:

```typescript
// In arenaStore.ts
const storeAudioChunk = (chunkNumber: number, audioData: ArrayBuffer) => {
  const chunks = JSON.parse(localStorage.getItem('audioChunks') || '{}');
  chunks[`chunk_${chunkNumber}`] = btoa(String.fromCharCode(...new Uint8Array(audioData)));
  localStorage.setItem('audioChunks', JSON.stringify(chunks));
};

// On rejoin, check local storage first before requesting from Gateway
const getAudioChunk = async (chunkNumber: number) => {
  const cached = JSON.parse(localStorage.getItem('audioChunks') || '{}');
  if (cached[`chunk_${chunkNumber}`]) {
    return atob(cached[`chunk_${chunkNumber}`]);
  }
  // Request from Gateway if not cached
  return await requestChunkFromGateway(chunkNumber);
};
```

=============================================================================
ERROR HANDLING
=============================================================================

**Case 1: Audio cache miss in Gateway**
- If chunk not in cache, regenerate text → TTS
- Store new chunks and send

**Case 2: Network failure during chunk send**
- Frontend detects missing chunks
- Requests resend of specific chunks
- Gateway sends only the missing ones

**Case 3: Multiple rejoins**
- Each rejoin gets undelivered chunks list
- Can rejoin multiple times without waste
- Each rejoin sent only new chunks

=============================================================================
MONITORING & LOGGING
=============================================================================

Backend logs chunk operations:
```
[CHUNKS] Stored chunk 3 for match-123:0 (bytes 8192-12288)
[CHUNKS] Found 3/6 undelivered chunks for match-123:0 (last sent: 1715340005)
[CHUNKS] Marked chunks delivered for match-123
```

Gateway should log:
```
[GATEWAY] Received CATCH_UP_BUFFER with 3 undelivered chunks
[GATEWAY] Sending chunk 3 (bytes 8192-12288)
[GATEWAY] All chunks sent, marked delivered
```

Frontend should log:
```
[AUDIO] Received chunk 3, resuming from 25s
[AUDIO] Audio stream complete
```

=============================================================================
TESTING CHECKLIST
=============================================================================

- [ ] PM generates speech
- [ ] 3 seconds of audio sent
- [ ] User disconnects
- [ ] User reconnects
- [ ] Gateway receives CATCH_UP_BUFFER with undelivered chunks
- [ ] Only unsent chunks received by frontend
- [ ] Audio resumes from 3-second mark (no full replay)
- [ ] Mark chunks delivered called

=============================================================================
"""

# Migration from old flow to new flow:
# OLD: Send entire audio on rejoin (wasteful)
# NEW: Send only undelivered chunks (efficient)
# 
# This reduces bandwidth, speeds up rejoin, and provides better UX
# because playback resumes seamlessly instead of restarting.
