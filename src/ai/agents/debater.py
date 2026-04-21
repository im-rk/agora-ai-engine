"""
Debate Response Generator: 4-Phase Pipeline with Streaming.

Architecture:
  Phase 1 (State Tracking): Parse debate transcript into clash matrix
    → Identify opponent claims, dropped arguments, vulnerabilities
  
  Phase 2 (Query Synthesis): Generate targeted search queries
    → Create 3-5 specific queries (not just keywords)
  
  Phase 3 (Retrieve & Re-Rank): Fetch and score evidence
    → Query pgvector, filter 15 results → top 3 "kill shots"
  
  Phase 4 (Generation): Stream response with callbacks
    → Assemble persona prompt, stream via Redis, publish tokens

Streaming Flow:
  LLM token generation
    ↓ (per token)
  RedisStreamingCallbackHandler.on_llm_new_token()
    ↓ (publishes to Redis)
  Redis Channel: "debate:{speaker_id}:response"
    ↓ (frontend subscribes)
  Real-time UI updates word-by-word
"""

import json
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from src.ai.clients.groq_client import get_groq_client
from src.ai.tools.rag_engine import RAGEngine
from src.ai.callbacks.redis_stream import RedisStreamingCallbackHandler
from src.ai.prompts.debater_prompts import (
    CLASH_MATRIX_PARSER_PROMPT,
    QUERY_SYNTHESIS_PROMPT,
    RESPONSE_GENERATION_PROMPT,
)
# Import AP-specific role constraints and functions
from src.ai.prompts.ap import (
    AP_ROLE_CONSTRAINTS,
    get_ap_role_instructions,
    normalize_ap_role,
    AP_CLASH_MATRIX_PARSER_PROMPT,
    AP_QUERY_SYNTHESIS_PROMPT,
    AP_RESPONSE_GENERATION_PROMPT,
)
from src.core.redis_client import get_redis_async
from src.core.config import settings
from src.core.database import SessionLocal
from src.repositories.ap.matches import log_ai_call


class DebaterAgent:
    """Multi-phase orchestrator for live debate responses with streaming."""

    def __init__(self, redis_client=None, rag_engine: Optional[RAGEngine] = None):
        """
        Initialize debater agent.
        
        Args:
            redis_client: Redis async client (auto-fetched if None)
            rag_engine: RAG engine for evidence retrieval (auto-created if None)
        """
        self.redis_client = redis_client or get_redis_async()
        self.rag_engine = rag_engine or RAGEngine()

    async def phase1_parse_clash_matrix(self, transcript: str, motion: str, session_id: Optional[str] = None) -> dict:
        """
        Phase 1: State Tracking - Parse transcript into clash matrix.
        
        Identifies:
        - Opponent's unanswered claims
        - Our dropped arguments
        - Vulnerabilities in their positions
        
        Args:
            transcript: Full debate transcript so far
            session_id: Debate session ID for logging
            
        Returns:
            dict with [opponent_claims, our_dropped_args, vulnerabilities]
        """
        llm = get_groq_client(streaming=False, temperature=0.1)

        prompt = [
            SystemMessage(content=AP_CLASH_MATRIX_PARSER_PROMPT.format(motion=motion)),
            HumanMessage(content=f"Parse this transcript:\n\n{transcript}")
        ]

        response = await llm.ainvoke(prompt)
        
        # Log the LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name="DebaterAgent:Phase1-ClashMatrixParser",
                    prompt_used=AP_CLASH_MATRIX_PARSER_PROMPT[:500],
                    model_version="llama-3.1-8b-instant",
                    temperature=0.1,
                    raw_output=response.content[:1000]
                )
            except Exception as log_error:
                print(f"[WARN] Failed to log AI call: {type(log_error).__name__}")
                db.rollback()
            finally:
                db.close()
        
        # Extract JSON from response
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "opponent_claims": [],
                "our_dropped_args": [],
                "vulnerabilities": []
            }

    async def phase2_generate_search_queries(
        self, 
        clash_matrix: dict,
        motion: str,
        speaker_role: str,
        session_id: Optional[str] = None
    ) -> list[str]:
        """
        Phase 2: Query Synthesis - Generate targeted search queries.
        
        Creates 3-5 specific queries tailored to speaker role:
        - Whips: Focus on rebuttals and comparative impact analysis
        - Other speakers: Focus on advancing arguments with evidence
        
        Args:
            clash_matrix: Output from Phase 1 (opponent claims, dropped args, vuln)
            speaker_role: AP speaker role (e.g., "Prime Minister (PM)", "Government Whip")
            session_id: Debate session ID for logging
            
        Returns:
            List of 3-5 optimized search queries
        """
        llm = get_groq_client(streaming=False, temperature=0.3)
        
        # Normalize role name for constraint lookup (state.schedule uses short names like "Prime Minister")
        normalized_role = normalize_ap_role(speaker_role)
        
        # Extract role constraint for query synthesis (AP-specific)
        role_constraint = ""
        if normalized_role in AP_ROLE_CONSTRAINTS:
            role_info = AP_ROLE_CONSTRAINTS[normalized_role]
            role_constraint = f"CONSTRAINT: {role_info['constraint']}\nFOCUS: {role_info['focus']}"
        else:
            role_constraint = f"Role: {speaker_role} - Advance your team's position with evidence"

        # Determine team position based on normalized role
        team_side = "Government" if "Government" in normalized_role or normalized_role.endswith("(PM)") or normalized_role.endswith("(DPM)") else "Opposition"
        if "Leader of Opposition" in normalized_role or normalized_role.endswith("(LO)") or normalized_role.endswith("(DLO)"):
            team_side = "Opposition"
        elif "Opposition Whip" in normalized_role:
            team_side = "Opposition"
        
        team_position = "You AFFIRM this motion (support it)" if team_side == "Government" else "You NEGATE this motion (oppose it)"

        # Use AP-specific query synthesis prompt
        prompt = [
            SystemMessage(content=AP_QUERY_SYNTHESIS_PROMPT.format(
                motion=motion,
                speaker_role=normalized_role,
                role_constraint=role_constraint,
                team_position=team_position
            )),
            HumanMessage(content=f"Generate search queries for:\n{json.dumps(clash_matrix, indent=2)}")
        ]

        response = await llm.ainvoke(prompt)
        
        # Log the LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name="DebaterAgent:Phase2-QuerySynthesis",
                    prompt_used=AP_QUERY_SYNTHESIS_PROMPT[:500],
                    model_version="llama-3.1-8b-instant",
                    temperature=0.3,
                    raw_output=response.content[:1000]
                )
            except Exception as log_error:
                print(f"[WARN] Failed to log AI call: {type(log_error).__name__}")
                db.rollback()
            finally:
                db.close()
        
        # Parse comma-separated or JSON array queries
        content = response.content.strip()
        if content.startswith("["):
            queries = json.loads(content)
        else:
            queries = [q.strip() for q in content.split("\n") if q.strip()]
        
        return queries[:5]  # Limit to 5 queries

    async def phase3_retrieve_and_rerank(
        self, 
        queries: list[str],
        match_id: str,
        side: str,
        top_k: int = 3
    ) -> list[dict]:
        """
        Phase 3: Retrieve & Re-Rank - Find top evidence pieces.
        
        Queries pgvector for each search query, collects top results,
        re-ranks by relevance score to find top 3 "kill shots".
        
        Args:
            queries: List of search queries from Phase 2
            match_id: Debate session ID
            side: Team side ("Government" or "Opposition")
            top_k: Number of final evidence pieces to return
            
        Returns:
            List of top-k evidence dicts with [id, text, score, source]
        """
        all_results = []
        
        for query in queries:
            # Hit pgvector for each query
            results = await self.rag_engine.aretrieve_counter_arguments(
                topic=query,
                match_id=match_id,
                side=side,
                k=5  # Get top 5 per query
            )
            all_results.extend(results)
        
        # De-duplicate and re-rank by relevance score
        unique_results = {}
        for result in all_results:
            result_id = result.get("id", result.get("text", "")[:50])
            if result_id not in unique_results:
                unique_results[result_id] = result
            else:
                # Keep highest score
                if result.get("score", 0) > unique_results[result_id].get("score", 0):
                    unique_results[result_id] = result
        
        # Sort by score and return top k
        sorted_results = sorted(
            unique_results.values(),
            key=lambda x: x.get("score", 0),
            reverse=True
        )
        
        return sorted_results[:top_k]

    async def phase4_generate_response_streaming(
        self,
        clash_matrix: dict,
        motion: str,
        speaker_role: str,
        evidence: list[dict],
        speaker_id: str,
        personality_trait: Optional[str] = None,
        session_id: Optional[str] = None,
        channel: Optional[str] = None
    ) -> str:
        """
        Phase 4: Generation - Stream response with callbacks.
        
        Assembles final prompt with clash matrix, evidence, and speaker
        persona. Uses streaming Groq client with RedisStreamingCallbackHandler
        to publish tokens in real-time.
        
        Args:
            clash_matrix: State from Phase 1
            speaker_role: "affirmative" or "negative"
            evidence: Top evidence pieces from Phase 3
            speaker_id: Unique speaker identifier
            personality_trait: Optional persona override (e.g., "aggressive", "analytical")
            session_id: Debate session ID for logging
            channel: Redis channel to stream tokens to
            
        Yields:
            Response tokens as they're generated (published to Redis)
            
        Returns:
            Full assembled response string
        """
        # Initialize streaming Groq client
        llm = get_groq_client(streaming=True, temperature=0.7)
        
        # Use provided channel or fallback securely
        channel = channel or f"debate:{speaker_id}:response"
        
        # Create streaming callback handler
        callback = RedisStreamingCallbackHandler(
            redis_client=self.redis_client,
            channel=channel
        )
        
        # Format evidence into readable ammo
        evidence_text = "\n".join([
            f"[Evidence {i+1}] {e.get('text', '')[:200]}... (Score: {e.get('score', 0):.2f})"
            for i, e in enumerate(evidence[:3])
        ])
        
        # Normalize role name for constraint lookup
        normalized_role = normalize_ap_role(speaker_role)
        
        # Get AP role-specific instructions using normalized role
        role_instructions = get_ap_role_instructions(normalized_role)
        
        # Determine team side from normalized role
        team_side = "Government" if "Government" in normalized_role or normalized_role.endswith("(PM)") or normalized_role.endswith("(DPM)") else "Opposition"
        if "Leader of Opposition" in normalized_role or normalized_role.endswith("(LO)") or normalized_role.endswith("(DLO)"):
            team_side = "Opposition"
        elif "Opposition Whip" in normalized_role:
            team_side = "Opposition"
        elif "Government" in normalized_role or "Whip" in normalized_role:
            team_side = "Government" if "Government" in normalized_role else "Opposition"
        
        # Assemble final prompt with AP-specific template (use normalized role in prompt)
        system_prompt = AP_RESPONSE_GENERATION_PROMPT.format(
            role_instructions=role_instructions,
            motion=motion,
            speaker_role=normalized_role,
            team_side=team_side,
            personality=personality_trait or "balanced",
            clash_matrix=json.dumps(clash_matrix),
            evidence=evidence_text if evidence else "No specific evidence found."
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Generate a compelling debate response.")
        ]
        
        # Stream response with request-scoped callbacks (only for this invocation)
        response = await llm.ainvoke(
            messages,
            config={"callbacks": [callback]}
        )
        
        # Log the streaming LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name="DebaterAgent:Phase4-ResponseGeneration",
                    prompt_used=AP_RESPONSE_GENERATION_PROMPT[:500],
                    model_version="llama-3.1-8b-instant",
                    temperature=0.7,
                    raw_output=response.content[:1000]
                )
            except Exception as log_error:
                print(f"[WARN] Failed to log AI call: {type(log_error).__name__}")
                db.rollback()
            finally:
                db.close()
        
        return response.content

    async def orchestrate_debater_response(
        self,
        transcript: str,
        motion: str,
        speaker_role: str,
        speaker_id: str,
        speaker_side: str,
        personality_trait: Optional[str] = None,
        session_id: Optional[str] = None,
        channel: Optional[str] = None
    ) -> str:
        """
        Main orchestrator: Execute all 4 phases sequentially.
        
        Full debate response pipeline:
          1. Parse transcript into clash matrix
          2. Generate targeted search queries
          3. Retrieve top evidence pieces
          4. Generate and stream response
        
        Args:
            transcript: Full debate transcript so far
            speaker_role: "affirmative" or "negative"
            speaker_id: Unique speaker identifier (for Redis channel)
            personality_trait: Optional persona (e.g., "aggressive", "analytical")
            session_id: Debate session ID for logging all LLM calls
            
        Returns:
            Complete debate response string with tokens published to Redis
        """
        # Phase 1: State Tracking
        clash_matrix = await self.phase1_parse_clash_matrix(transcript, motion, session_id)
        
        # Phase 2: Query Synthesis
        queries = await self.phase2_generate_search_queries(clash_matrix, motion, speaker_role, session_id)
        
        # Phase 3: Retrieve & Re-Rank
        evidence = await self.phase3_retrieve_and_rerank(
            queries=queries, 
            match_id=session_id, 
            side=speaker_side, 
            top_k=3
        )
        
        # Phase 4: Generation with Streaming
        response = await self.phase4_generate_response_streaming(
            clash_matrix=clash_matrix,
            motion=motion,
            speaker_role=speaker_role,
            evidence=evidence,
            speaker_id=speaker_id,
            personality_trait=personality_trait,
            session_id=session_id,
            channel=channel
        )
        
        return response
