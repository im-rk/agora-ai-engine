"""
Adjudication Agent: 5-Phase Hybrid-Weighted Evaluation Algorithm.

Architecture (5 Phases):
  Phase 1 (Neutral Theme Extraction): Extract 3-5 macro-clashes from transcript
    → Identifies core themes, not specific arguments
  
  Phase 2 (Weighted Clash Matrix): Build WCM with Weight (1-5) & Delta (-2 to +2)
    → Calculates Net Logic Score = Sum(Weight × Delta)
  
  Phase 3 (Mathematical Breakdown): Chain of Thought reasoning per clash
    → Shows EXACTLY why each team won/lost each clash
  
  Phase 4 (WUDC Pillar Analysis): Grade Matter (Logic), Manner (Delivery), 
           Method (Structure), Role (Rules) independently
    → Prevents bias by not letting one pillar dominate
  
  Phase 5 (Structured Output): Generate Pydantic JSON schema with:
    → WCM matrix, speaker scores, pillar breakdown, adjudication statement

Key Features:
  ✓ Mathematically traceable (every score backed by formula)
  ✓ Anti-bias (multiple evaluation pillars)
  ✓ CoT reasoning (explains every decision)
  ✓ Structured JSON (ready for React dashboard)
  ✓ Logging (all LLM calls recorded)
"""

import json
from typing import Optional
from dataclasses import dataclass
from langchain_core.messages import SystemMessage, HumanMessage

from src.ai.clients.groq_client import get_groq_client
from src.ai.prompts.adjudicator_prompts import (
    MACRO_CLASH_EXTRACTION_PROMPT,
    WEIGHTED_CLASH_MATRIX_PROMPT,
    WUDC_PILLAR_ANALYSIS_PROMPT,
    SPEAKER_PERFORMANCE_PROMPT,
    FINAL_ADJUDICATION_SUMMARY_PROMPT,
)
from src.core.database import SessionLocal
from src.repositories.ap.matches import log_ai_call


@dataclass
class Clash:
    """Represents a single macro-clash in the debate."""
    id: int
    theme: str
    description: str
    government_position: str
    opposition_position: str


@dataclass
class WCMClash:
    """Weighted Clash Matrix entry (Phase 2 output)."""
    clash_id: int
    clash_theme: str
    weight: int  # 1-5
    weight_reasoning: str
    delta: int  # -2 to +2
    delta_reasoning: str
    weighted_score: int  # = weight * delta


class AdjudicatorAgent:
    """
    5-Phase Hybrid-Weighted Evaluation Algorithm for debate adjudication.
    
    Produces mathematically rigorous, bias-resistant scoring with full
    Chain of Thought transparency and WUDC pillar adherence.
    """

    def __init__(self):
        """Initialize adjudicator agent."""
        pass

    async def phase1_extract_macro_clashes(
        self, 
        transcript: str,
        session_id: Optional[str] = None
    ) -> list[Clash]:
        """
        Phase 1: Neutral Theme Extraction.
        
        Identifies 3-5 core macro-themes (thematic clashes) that defined
        the debate, not specific arguments.
        
        Args:
            transcript: Complete debate transcript (all turns)
            session_id: Debate session ID for logging
            
        Returns:
            List of Clash objects with theme, description, positions
        """
        llm = get_groq_client(streaming=False, temperature=0.2)

        prompt = [
            SystemMessage(content=MACRO_CLASH_EXTRACTION_PROMPT.format(
                transcript=transcript
            )),
            HumanMessage(content="Extract the macro-clashes from this debate.")
        ]

        response = await llm.ainvoke(prompt)
        
        # Log the LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name="AdjudicatorAgent:Phase1-MacroClashExtraction",
                    prompt_used=MACRO_CLASH_EXTRACTION_PROMPT[:500],
                    model_version="llama-3.1-8b-instant",
                    temperature=0.2,
                    raw_output=response.content[:1000]
                )
            except Exception as log_error:
                print(f"[WARN] Failed to log AI call: {type(log_error).__name__}")
                db.rollback()
            finally:
                db.close()
        
        # Parse JSON response
        try:
            result = json.loads(response.content)
            clashes = []
            for c in result.get("clashes", []):
                clashes.append(Clash(
                    id=c["id"],
                    theme=c["theme"],
                    description=c["description"],
                    government_position=c["government_position"],
                    opposition_position=c["opposition_position"]
                ))
            return clashes
        except json.JSONDecodeError:
            print("[ERROR] Failed to parse macro-clashes JSON")
            return []

    async def phase2_build_weighted_clash_matrix(
        self,
        clashes: list[Clash],
        transcript: str,
        session_id: Optional[str] = None
    ) -> tuple[list[WCMClash], float]:
        """
        Phase 2: Weighted Clash Matrix Construction.
        
        For each clash, assigns:
        - Weight (1-5): Importance to debate outcome
        - Delta (-2 to +2): Which team won
        - Weighted Score = Weight × Delta
        
        Then calculates Net Logic Score = Sum(Weighted Scores)
        
        Args:
            clashes: List of Clash objects from Phase 1
            transcript: Complete debate transcript
            session_id: Debate session ID for logging
            
        Returns:
            Tuple of (WCM clash list, Net Logic Score)
        """
        llm = get_groq_client(streaming=False, temperature=0.2)

        clashes_json = json.dumps([
            {
                "id": c.id,
                "theme": c.theme,
                "description": c.description,
                "gov_position": c.government_position,
                "opp_position": c.opposition_position
            }
            for c in clashes
        ], indent=2)

        prompt = [
            SystemMessage(content=WEIGHTED_CLASH_MATRIX_PROMPT.format(
                clashes=clashes_json,
                transcript=transcript
            )),
            HumanMessage(content="Build the WCM matrix and calculate Net Logic Score.")
        ]

        response = await llm.ainvoke(prompt)
        
        # Log the LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name="AdjudicatorAgent:Phase2-WeightedClashMatrix",
                    prompt_used=WEIGHTED_CLASH_MATRIX_PROMPT[:500],
                    model_version="llama-3.1-8b-instant",
                    temperature=0.2,
                    raw_output=response.content[:1000]
                )
            except Exception as log_error:
                print(f"[WARN] Failed to log AI call: {type(log_error).__name__}")
                db.rollback()
            finally:
                db.close()
        
        # Parse JSON response
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
            wcm_clashes = []
            for item in result.get("wcm_matrix", []):
                wcm_clashes.append(WCMClash(
                    clash_id=item["clash_id"],
                    clash_theme=item["clash_theme"],
                    weight=item["weight"],
                    weight_reasoning=item["weight_reasoning"],
                    delta=item["delta"],
                    delta_reasoning=item["delta_reasoning"],
                    weighted_score=item["weighted_score"]
                ))
            
            net_logic_score = float(result.get("net_logic_score", 0))
            return wcm_clashes, net_logic_score
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse WCM JSON: {e}")
            return [], 0.0

    async def phase3_analyze_wudc_pillars(
        self,
        wcm_clashes: list[WCMClash],
        net_logic_score: float,
        transcript: str,
        speaker_info: str,
        session_id: Optional[str] = None
    ) -> dict:
        """
        Phase 3: WUDC Pillar Analysis (Anti-Bias Adjustment).
        
        Grades independently on 4 pillars:
        - Matter (Logic): Based on WCM math (0-25)
        - Manner (Delivery): Persuasiveness, naturalism (0-25)
        - Method (Structure): Organization, case construction (0-25)
        - Role (Rules): Speaker responsibility fulfillment (0-25)
        
        Team with higher total (0-100) wins debate.
        
        Args:
            wcm_clashes: WCM matrix from Phase 2
            net_logic_score: Net Logic Score from Phase 2
            transcript: Complete debate transcript
            speaker_info: Speaker breakdown (roles, number of turns)
            session_id: Debate session ID for logging
            
        Returns:
            Dict with pillar scores and breakdown for both teams
        """
        llm = get_groq_client(streaming=False, temperature=0.3)

        wcm_matrix_json = json.dumps([
            {
                "clash_id": c.clash_id,
                "theme": c.clash_theme,
                "weight": c.weight,
                "delta": c.delta,
                "weighted_score": c.weighted_score
            }
            for c in wcm_clashes
        ], indent=2)

        prompt = [
            SystemMessage(content=WUDC_PILLAR_ANALYSIS_PROMPT.format(
                wcm_matrix=wcm_matrix_json,
                net_logic_score=net_logic_score,
                transcript=transcript,
                speaker_info=speaker_info
            )),
            HumanMessage(content="Grade both teams on the 4 WUDC pillars.")
        ]

        response = await llm.ainvoke(prompt)
        
        # Log the LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name="AdjudicatorAgent:Phase3-WUDCPillarAnalysis",
                    prompt_used=WUDC_PILLAR_ANALYSIS_PROMPT[:500],
                    model_version="llama-3.1-8b-instant",
                    temperature=0.3,
                    raw_output=response.content[:1000]
                )
            except Exception as log_error:
                print(f"[WARN] Failed to log AI call: {type(log_error).__name__}")
                db.rollback()
            finally:
                db.close()
        
        # Parse JSON response
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip(), strict=False)
            return result
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse WUDC pillars JSON: {e}")
            print(f"Raw response: {response.content}")
            return {}

    async def phase4_grade_speakers(
        self,
        speaker_roles: list[str],
        debate_format: str,
        clashes: list[Clash],
        pillar_scores: dict,
        transcript: str,
        session_id: Optional[str] = None
    ) -> dict:
        """
        Phase 4: Individual Speaker Grading.
        
        Grades each speaker (0-100) on:
        - Argument quality (0-10)
        - Evidence usage (0-10)
        - Responsiveness (0-10)
        - Structure (0-10)
        - Persona fit (0-10)
        Final score = sum * 2
        
        Args:
            speaker_roles: List of speaker roles (in order)
            debate_format: Format (AP, BP, etc.)
            clashes: Macro-clashes from Phase 1
            pillar_scores: Pillar breakdown from Phase 3
            transcript: Complete debate transcript
            session_id: Debate session ID for logging
            
        Returns:
            Dict with speaker scores and feedback
        """
        llm = get_groq_client(streaming=False, temperature=0.3)

        clashes_json = json.dumps([
            {
                "id": c.id,
                "theme": c.theme,
                "description": c.description
            }
            for c in clashes
        ], indent=2)

        prompt = [
            SystemMessage(content=SPEAKER_PERFORMANCE_PROMPT.format(
                format=debate_format,
                speaker_roles=json.dumps(speaker_roles),
                clashes=clashes_json,
                pillar_scores=json.dumps(pillar_scores, indent=2),
                transcript=transcript
            )),
            HumanMessage(content="Grade each speaker on their individual performance.")
        ]

        response = await llm.ainvoke(prompt)
        
        # Log the LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name="AdjudicatorAgent:Phase4-SpeakerGrading",
                    prompt_used=SPEAKER_PERFORMANCE_PROMPT[:500],
                    model_version="llama-3.1-8b-instant",
                    temperature=0.3,
                    raw_output=response.content[:1000]
                )
            except Exception as log_error:
                print(f"[WARN] Failed to log AI call: {type(log_error).__name__}")
                db.rollback()
            finally:
                db.close()
        
        # Parse JSON response
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            result = json.loads(content.strip(), strict=False)
            return result
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse speaker scores JSON: {e}")
            return {}

    async def phase5_generate_summary(
        self,
        wcm_summary: dict,
        pillar_breakdown: dict,
        speaker_scores: dict,
        session_id: Optional[str] = None
    ) -> dict:
        """
        Phase 5: Final Adjudication Summary.
        
        Generates:
        - Brief adjudication statement (why team won)
        - Top 3 key decision points
        - Highlights standout performances
        - Development areas for both teams
        
        Args:
            wcm_summary: WCM results from Phase 2
            pillar_breakdown: Pillar scores from Phase 3
            speaker_scores: Speaker scores from Phase 4
            session_id: Debate session ID for logging
            
        Returns:
            Dict with adjudication statement and key decisions
        """
        llm = get_groq_client(streaming=False, temperature=0.4)

        prompt = [
            SystemMessage(content=FINAL_ADJUDICATION_SUMMARY_PROMPT.format(
                wcm_summary=json.dumps(wcm_summary, indent=2),
                pillar_breakdown=json.dumps(pillar_breakdown, indent=2),
                speaker_scores=json.dumps(speaker_scores, indent=2)
            )),
            HumanMessage(content="Generate the final adjudication summary.")
        ]

        response = await llm.ainvoke(prompt)
        
        # Log the LLM call
        if session_id:
            db = SessionLocal()
            try:
                log_ai_call(
                    db=db,
                    session_id=session_id,
                    agent_name="AdjudicatorAgent:Phase5-FinalSummary",
                    prompt_used=FINAL_ADJUDICATION_SUMMARY_PROMPT[:500],
                    model_version="llama-3.1-8b-instant",
                    temperature=0.4,
                    raw_output=response.content[:1000]
                )
            except Exception as log_error:
                print(f"[WARN] Failed to log AI call: {type(log_error).__name__}")
                db.rollback()
            finally:
                db.close()
        
        # Parse JSON response
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            result = json.loads(content.strip(), strict=False)
            return result
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse summary JSON: {e}")
            return {}

    async def orchestrate_adjudication(
        self,
        transcript: str,
        debate_format: str,
        speaker_roles: list[str],
        session_id: Optional[str] = None
    ) -> dict:
        """
        Main orchestrator: Execute all 5 phases sequentially.
        
        Complete adjudication pipeline:
          1. Extract macro-clashes (3-5 themes)
          2. Build WCM with weights and deltas
          3. Analyze WUDC pillars (Matter, Manner, Method, Role)
          4. Grade individual speakers (0-100)
          5. Generate summary with CoT reasoning
        
        Args:
            transcript: Complete debate transcript
            debate_format: Format (AP, BP, etc.)
            speaker_roles: List of speaker roles
            session_id: Debate session ID for logging
            
        Returns:
            Complete adjudication result dict with all phases
        """
        print("[ADJUDICATOR] Starting 5-phase adjudication...")
        
        # 1: Extract Macro-Clashes
        print("[ADJUDICATOR] Phase 1: Extracting macro-clashes...")
        clashes = await self.phase1_extract_macro_clashes(
            transcript=transcript,
            session_id=session_id
        )
        print(f"[ADJUDICATOR] Found {len(clashes)} macro-clashes")
        
        # 2: Build WCM Matrix
        print("[ADJUDICATOR] Phase 2: Building Weighted Clash Matrix...")
        wcm_clashes, net_logic_score = await self.phase2_build_weighted_clash_matrix(
            clashes=clashes,
            transcript=transcript,
            session_id=session_id
        )
        print(f"[ADJUDICATOR] Net Logic Score: {net_logic_score}")
        
        # Format speaker info
        speaker_info = f"Format: {debate_format}\nSpeakers: {', '.join(speaker_roles)}"
        
        # 3: Analyze WUDC Pillars
        print("[ADJUDICATOR] Phase 3: Analyzing WUDC pillars...")
        pillar_breakdown = await self.phase3_analyze_wudc_pillars(
            wcm_clashes=wcm_clashes,
            net_logic_score=net_logic_score,
            transcript=transcript,
            speaker_info=speaker_info,
            session_id=session_id
        )
        print("[ADJUDICATOR] Pillar analysis complete")
        
        # 4: Grade Speakers
        print("[ADJUDICATOR] Phase 4: Grading speakers...")
        speaker_scores = await self.phase4_grade_speakers(
            speaker_roles=speaker_roles,
            debate_format=debate_format,
            clashes=clashes,
            pillar_scores=pillar_breakdown,
            transcript=transcript,
            session_id=session_id
        )
        print("[ADJUDICATOR] Speaker grading complete")
        
        # 5: Generate Summary
        print("[ADJUDICATOR] Phase 5: Generating summary...")
        summary = await self.phase5_generate_summary(
            wcm_summary={
                "clashes": [c.__dict__ for c in wcm_clashes],
                "net_logic_score": net_logic_score
            },
            pillar_breakdown=pillar_breakdown,
            speaker_scores=speaker_scores,
            session_id=session_id
        )
        print("[ADJUDICATOR] Adjudication complete!")
        
        # Final Results
        result = {
            "clashes": [c.__dict__ for c in clashes],
            "wcm_matrix": [c.__dict__ for c in wcm_clashes],
            "net_logic_score": net_logic_score,
            "pillar_breakdown": pillar_breakdown,
            "speaker_scores": speaker_scores,
            "summary": summary
        }
        
        return result
