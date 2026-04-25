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
from src.core.redis_client import get_redis_async
from src.core.config import settings
from src.core.database import SessionLocal
from src.repositories.ap.matches import log_ai_call


class DebaterAgent:
    """Multi-phase orchestrator for live debate responses with streaming."""

    DIFFICULTY_PROFILES = {
        "easy": {
            "query_style": "Use broad, high-signal queries for beginner-friendly evidence.",
            "response_style": (
                "Keep arguments simple and clear. Use everyday language, avoid jargon, "
                "focus on 1-2 core clashes, and make the structure easy to follow."
            ),
        },
        "medium": {
            "query_style": "Use balanced queries with both conceptual and data-backed evidence.",
            "response_style": (
                "Use moderate complexity. Cover 2-3 clashes with clear weighing and concise "
                "comparative analysis."
            ),
        },
        "hard": {
            "query_style": "Use precise, technical queries targeting nuanced comparative impacts.",
            "response_style": (
                "Use advanced debate strategy: layered rebuttals, stakeholder vulnerability "
                "analysis, and explicit impact calculus."
            ),
        },
    }

    def __init__(self, format_type: str = "ap", redis_client=None, rag_engine: Optional[RAGEngine] = None):
        """
        Initialize debater agent.
        
        Args:
            format_type: Debate format - "ap" (Asian Parliamentary) or "bp" (British Parliamentary)
            redis_client: Redis async client (auto-fetched if None)
            rag_engine: RAG engine for evidence retrieval (auto-created if None)
            
        Raises:
            ValueError: If format_type is not "ap" or "bp"
        """
        self.redis_client = redis_client or get_redis_async()
        self.rag_engine = rag_engine or RAGEngine()
        self.format_type = format_type.lower()
        
        # Import format-specific prompts and functions
        if self.format_type == "ap":
            from src.ai.prompts.ap import (
                AP_ROLE_CONSTRAINTS,
                get_ap_role_instructions,
                normalize_ap_role,
                AP_CLASH_MATRIX_PARSER_PROMPT,
                AP_QUERY_SYNTHESIS_PROMPT,
                AP_RESPONSE_GENERATION_PROMPT,
            )
            self.role_constraints = AP_ROLE_CONSTRAINTS
            self.get_role_instructions = get_ap_role_instructions
            self.normalize_role = normalize_ap_role
            self.clash_matrix_prompt = AP_CLASH_MATRIX_PARSER_PROMPT
            self.query_synthesis_prompt = AP_QUERY_SYNTHESIS_PROMPT
            self.response_generation_prompt = AP_RESPONSE_GENERATION_PROMPT
        
        elif self.format_type == "bp":
            from src.ai.prompts.bp import (
                BP_ROLE_CONSTRAINTS,
                get_bp_role_instructions,
                normalize_bp_role,
                BP_CLASH_MATRIX_PARSER_PROMPT,
                BP_QUERY_SYNTHESIS_PROMPT,
                BP_RESPONSE_GENERATION_PROMPT,
            )
            self.role_constraints = BP_ROLE_CONSTRAINTS
            self.get_role_instructions = get_bp_role_instructions
            self.normalize_role = normalize_bp_role
            self.clash_matrix_prompt = BP_CLASH_MATRIX_PARSER_PROMPT
            self.query_synthesis_prompt = BP_QUERY_SYNTHESIS_PROMPT
            self.response_generation_prompt = BP_RESPONSE_GENERATION_PROMPT
        
        else:
            raise ValueError(f"Unsupported debate format: {self.format_type}. Use 'ap' or 'bp'.")

    def _normalize_difficulty(self, difficulty_level: Optional[str]) -> str:
        """Normalize caller-provided difficulty labels to easy/medium/hard."""
        if not difficulty_level:
            return "easy"

        key = str(difficulty_level).strip().lower()
        mapping = {
            "easy": "easy",
            "beginner": "easy",
            "medium": "medium",
            "intermediate": "medium",
            "hard": "hard",
            "advanced": "hard",
        }
        return mapping.get(key, "easy")

    def _build_difficulty_instructions(self, difficulty_level: Optional[str]) -> tuple[str, str, str]:
        """Return normalized difficulty plus query/response guidance."""
        normalized = self._normalize_difficulty(difficulty_level)
        profile = self.DIFFICULTY_PROFILES[normalized]
        return normalized, profile["query_style"], profile["response_style"]

    async def phase1_parse_clash_matrix(self, transcript: str, motion: str, session_id: Optional[str] = None) -> dict:
        """
        Phase 1: State Tracking - Parse transcript into clash matrix.
        
        Identifies:
        - Opponent's unanswered claims
        - Our dropped arguments
        - Vulnerabilities in their positions
        
        Args:
            transcript: Full debate transcript so far
            motion: Debate motion
            session_id: Debate session ID for logging
            
        Returns:
            dict with [opponent_claims, our_dropped_args, vulnerabilities]
        """
        llm = get_groq_client(streaming=False, temperature=0.1)

        prompt = [
            SystemMessage(content=self.clash_matrix_prompt.format(motion=motion)),
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
                    agent_name=f"DebaterAgent:Phase1-ClashMatrixParser ({self.format_type.upper()})",
                    prompt_used=self.clash_matrix_prompt[:500],
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
        difficulty_level: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> list[str]:
        """
        Phase 2: Query Synthesis - Generate targeted search queries.
        
        Creates 3-5 specific queries tailored to speaker role:
        - Whips: Focus on rebuttals and comparative impact analysis
        - Other speakers: Focus on advancing arguments with evidence
        
        Args:
            clash_matrix: Output from Phase 1 (opponent claims, dropped args, vuln)
            motion: Debate motion
            speaker_role: Speaker role (e.g., "Prime Minister", "Government Whip")
            session_id: Debate session ID for logging
            
        Returns:
            List of 3-5 optimized search queries
        """
        llm = get_groq_client(streaming=False, temperature=0.3)
        difficulty, query_difficulty_style, _ = self._build_difficulty_instructions(difficulty_level)
        
        # Normalize role name for constraint lookup (state.schedule uses short names)
        normalized_role = self.normalize_role(speaker_role)
        
        # Extract role constraint for query synthesis
        role_constraint = ""
        if normalized_role in self.role_constraints:
            role_info = self.role_constraints[normalized_role]
            role_constraint = f"CONSTRAINT: {role_info['constraint']}\nFOCUS: {role_info['focus']}"
        else:
            role_constraint = f"Role: {speaker_role} - Advance your team's position with evidence"

        # Determine team position based on normalized role
        team_side = "Government" if "Government" in normalized_role or normalized_role.endswith("(PM)") or normalized_role.endswith("(DPM)") or normalized_role.endswith("(MG)") or normalized_role.endswith("(GW)") else "Opposition"
        if "Leader of Opposition" in normalized_role or normalized_role.endswith("(LO)") or normalized_role.endswith("(DLO)") or normalized_role.endswith("(MO)") or normalized_role.endswith("(OW)"):
            team_side = "Opposition"
        
        team_position = "You AFFIRM this motion (support it)" if team_side == "Government" else "You NEGATE this motion (oppose it)"

        # Use format-specific query synthesis prompt
        prompt = [
            SystemMessage(content=self.query_synthesis_prompt.format(
                motion=motion,
                speaker_role=normalized_role,
                role_constraint=role_constraint,
                team_position=team_position
            )),
            HumanMessage(content=(
                f"Difficulty: {difficulty.upper()}\n"
                f"Difficulty Guidance: {query_difficulty_style}\n\n"
                f"Generate search queries for:\n{json.dumps(clash_matrix, indent=2)}"
            ))
        ]

        response = await llm.ainvoke(prompt)
        
        # Log the LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name=f"DebaterAgent:Phase2-QuerySynthesis ({self.format_type.upper()})",
                    prompt_used=self.query_synthesis_prompt[:500],
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
        difficulty_level: Optional[str] = None,
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
            motion: Debate motion
            speaker_role: Speaker role (e.g., "Prime Minister", "Government Whip")
            evidence: Top evidence pieces from Phase 3
            speaker_id: Unique speaker identifier
            personality_trait: Optional persona override (e.g., "aggressive", "analytical")
            session_id: Debate session ID for logging
            channel: Redis channel to stream tokens to
            
        Returns:
            Full assembled response string
        """
        # Initialize streaming Groq client
        llm = get_groq_client(streaming=True, temperature=0.7)
        difficulty, _, response_difficulty_style = self._build_difficulty_instructions(difficulty_level)
        
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
        normalized_role = self.normalize_role(speaker_role)
        
        # Get format-specific role instructions using normalized role
        role_instructions = self.get_role_instructions(normalized_role)
        
        # Determine team side from normalized role
        team_side = "Government" if "Government" in normalized_role or normalized_role.endswith("(PM)") or normalized_role.endswith("(DPM)") or normalized_role.endswith("(MG)") or normalized_role.endswith("(GW)") else "Opposition"
        if "Leader of Opposition" in normalized_role or normalized_role.endswith("(LO)") or normalized_role.endswith("(DLO)") or normalized_role.endswith("(MO)") or normalized_role.endswith("(OW)"):
            team_side = "Opposition"
        
        # Assemble final prompt with format-specific template
        system_prompt = self.response_generation_prompt.format(
            role_instructions=role_instructions,
            motion=motion,
            speaker_role=normalized_role,
            team_side=team_side,
            team_position=team_side,
            personality=personality_trait or "balanced",
            clash_matrix=json.dumps(clash_matrix),
            evidence=evidence_text if evidence else "No specific evidence found."
        )
        system_prompt += (
            f"\n\n--- DIFFICULTY TARGET ---\n"
            f"Student Difficulty: {difficulty.upper()}\n"
            f"Guidance: {response_difficulty_style}\n"
            f"Do not deviate from this difficulty level."
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
                    agent_name=f"DebaterAgent:Phase4-ResponseGeneration ({self.format_type.upper()})",
                    prompt_used=self.response_generation_prompt[:500],
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
        difficulty_level: Optional[str] = None,
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
        
        Format-Aware Behavior:
        - If initialized with format_type="ap": Uses AP-specific prompts and role constraints
        - If initialized with format_type="bp": Uses BP-specific prompts and role constraints
        
        Args:
            transcript: Full debate transcript so far
            motion: Debate motion/proposition
            speaker_role: Speaker role name (e.g., "Prime Minister", "Member of Government")
            speaker_id: Unique speaker identifier (for Redis channel)
            speaker_side: Team side ("Government" or "Opposition")
            difficulty_level: Difficulty target (easy/medium/hard or beginner/intermediate/advanced)
            personality_trait: Optional persona (e.g., "aggressive", "analytical")
            session_id: Debate session ID for logging all LLM calls
            channel: Custom Redis channel (auto-generated if None)
            
        Returns:
            Complete debate response string with tokens published to Redis
            
        Raises:
            ValueError: If format_type was invalid during initialization
        """
        # Phase 1: State Tracking
        clash_matrix = await self.phase1_parse_clash_matrix(transcript, motion, session_id)
        
        # Phase 2: Query Synthesis
        queries = await self.phase2_generate_search_queries(
            clash_matrix,
            motion,
            speaker_role,
            difficulty_level,
            session_id,
        )
        
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
            difficulty_level=difficulty_level,
            personality_trait=personality_trait,
            session_id=session_id,
            channel=channel
        )
        
        return response
