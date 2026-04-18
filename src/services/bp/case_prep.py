"""
British Parliamentary (BP) Case Prep Service.

Business logic layer for case preparation workflow.

Responsibilities:
1. Verify user is a participant in the match
2. Create empty CasePrep record
3. Call Prep Coach AI agent (role-specific context)
4. Validate AI-generated response
5. Persist case prep data to database
6. Generate embeddings for semantic search
7. Log AI call for observability

Key difference from AP:
- format="british_parliamentary" passed to AI agent
- BPTeam/BPRole used instead of DebateSide/APRole
"""

import logging
import json
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from src.repositories.bp.case_prep import BPCasePrepRepository
from src.ai.agents.prep_coach import generate_case_prep
from src.schemas.bp.case_prep import (
    CasePrepResponse,
    GenerateCasePrepRequest,
)

logger = logging.getLogger(__name__)


class BPCasePrepService:
    """
    Service for BP case prep operations.
    
    Orchestrates the complete case prep workflow:
    AI agent → validation → persistence → embeddings → logging
    """
    
    def __init__(self):
        """Initialize service with repository."""
        self.repository = BPCasePrepRepository()
    
    # GENERATE CASE PREP
        
    async def generate_case_prep(
        self,
        db: Session,
        user_id: str,
        match_id: str,
        request: GenerateCasePrepRequest
    ) -> CasePrepResponse:
        """
        Generate role-specific case prep for user in BP match.
        
        Complete Workflow:
        1. Create empty CasePrep record
        2. Call Prep Coach agent (role-specific, BP format)
        3. Validate AI response
        4. Update CasePrep with generated data
        5. Generate embeddings (for semantic search)
        6. Log AI call (for observability)
        7. Return formatted response
        
        Business Rules:
        - User must be authenticated
        - Only one case prep per user per match
        - Case prep is role-specific (8 BP roles)
        - BP closing teams MUST provide extension arguments
        
        Args:
            db (Session): Database session
            user_id (str): UUID of user generating case prep
            match_id (str): UUID of match
            request (GenerateCasePrepRequest): Motion, team, and role
        
        Returns:
            CasePrepResponse: Generated case prep with all guidance
        
        Raises:
            ValueError: If invalid state or AI generation fails
            Exception: If database operation fails
        """
        try:
            logger.info(f"Generating BP case prep for user {user_id} in match {match_id}")
            
            # Extract team and role from request
            user_team = request.team
            user_role = request.role
            
            # Map BPTeam to side for CasePrep record
            team_to_side = {
                "opening_government": "Government",
                "opening_opposition": "Opposition",
                "closing_government": "Government",
                "closing_opposition": "Opposition",
            }
            user_side = team_to_side.get(user_team.value, "Government")
            
            logger.info(f"User {user_id} role: {user_role} on {user_team} team (side: {user_side})")
            
            # Retrieve the CasePrep record that was created during match creation
            case_prep_db = self.repository.get_case_prep_by_user_match(
                db=db,
                user_id=user_id,
                match_id=match_id
            )
            
            if not case_prep_db:
                raise ValueError("Case prep record not found for this match. The match might be corrupted.")
            
            # Call Prep Coach AI agent with BP format
            ai_response = await generate_case_prep(
                motion_text=request.motion,
                side=user_side,
                format="british_parliamentary"    # ← BP format (AP uses "asian_parliamentary")
            )
            
            # Validate AI response structure
            if not isinstance(ai_response, dict):
                raise ValueError("AI response must be a dictionary")
            
            required_fields = {"model_definition", "arguments", "counter_arguments", "evidence"}
            missing = required_fields - set(ai_response.keys())
            if missing:
                raise ValueError(f"AI response missing required fields: {missing}")
            
            # Update CasePrep with AI-generated data
            case_prep_db = self.repository.update_case_prep(
                db=db,
                case_prep_id=str(case_prep_db.id),
                model_definition=ai_response.get("model_definition", ""),
                arguments=ai_response.get("arguments", []),
                counter_arguments=ai_response.get("counter_arguments", []),
                evidence=ai_response.get("evidence", []),
                role_brief=None,
                tips=[]
            )
            
            # Generate vector embeddings for semantic search
            embedding_texts = []
            
            # Extract argument claims for embedding
            for arg in ai_response.get("arguments", []):
                if isinstance(arg, dict) and "claim" in arg:
                    embedding_texts.append((arg["claim"], "argument_claim"))
                    if "reasoning" in arg:
                        embedding_texts.append((arg["reasoning"], "argument_reasoning"))
            
            # Extract counter-arguments (already strings)
            for counter_arg in ai_response.get("counter_arguments", []):
                if counter_arg:
                    embedding_texts.append((counter_arg, "counter_argument"))
            
            # Extract evidence (already strings)
            for evidence in ai_response.get("evidence", []):
                if evidence:
                    embedding_texts.append((evidence, "evidence"))
            
            # Save embeddings to PostgreSQL via repository
            if embedding_texts:
                self.repository.save_embeddings(db, str(case_prep_db.id), embedding_texts)
            
            # Log AI call for observability
            self.repository.save_ai_call_log(
                db=db,
                match_id=match_id,
                agent_name="prep_coach",
                prompt_used=json.dumps({
                    "motion": request.motion,
                    "team": user_team.value,
                    "role": user_role.value,
                    "format": "british_parliamentary"
                }),
                model_version="gpt-4o-mini",
                temperature=0.7,
                raw_output=json.dumps(ai_response, indent=2)
            )
            
            logger.info(f"BP Case prep generated: {case_prep_db.id}")
            
            return CasePrepResponse(
                id=str(case_prep_db.id),
                user_id=str(case_prep_db.user_id),
                match_id=match_id,
                team=user_team,
                role=user_role,
                model_definition=case_prep_db.model_definition or "",
                arguments=case_prep_db.arguments or [],
                counter_arguments=case_prep_db.counter_arguments or [],
                evidence=case_prep_db.evidence or []
            )
            
        except ValueError as e:
            logger.warning(f"Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to generate BP case prep: {str(e)}")
            db.rollback()
            raise
    
    # RETRIEVE CASE PREP
    
    async def get_case_prep(
        self,
        db: Session,
        user_id: str,
        match_id: str
    ) -> Optional[CasePrepResponse]:
        """
        Get case prep for current user in a BP match.
        
        Args:
            db (Session): Database session
            user_id (str): UUID of user
            match_id (str): UUID of match
        
        Returns:
            Optional[CasePrepResponse]: User's case prep if exists
        """
        try:
            # Get user's case prep for this match
            case_prep_db = self.repository.get_case_prep_by_user_match(
                db, user_id, match_id
            )
            
            if not case_prep_db:
                logger.info(f"No case prep found for user {user_id} in match {match_id}")
                return None
            
            # Need to get the DebateSession to know the role!
            from src.models.debate import DebateSession
            from src.schemas.bp.matches import BPTeam
            session = db.query(DebateSession).filter(DebateSession.id == match_id).first()
            if not session:
                return None
                
            human_role = session.human_role
            side = case_prep_db.side.lower()
            closing_roles = {"member_of_government", "member_of_opposition", "government_whip", "opposition_whip"}
            is_closing = human_role.lower() in closing_roles
            
            if side == "government":
                human_team = BPTeam.CLOSING_GOVERNMENT if is_closing else BPTeam.OPENING_GOVERNMENT
            else:
                human_team = BPTeam.CLOSING_OPPOSITION if is_closing else BPTeam.OPENING_OPPOSITION
            
            return CasePrepResponse(
                id=str(case_prep_db.id),
                user_id=str(case_prep_db.user_id),
                match_id=match_id,
                team=human_team,
                role=human_role,
                model_definition=case_prep_db.model_definition or "",
                arguments=case_prep_db.arguments or [],
                counter_arguments=case_prep_db.counter_arguments or [],
                evidence=case_prep_db.evidence or []
            )
            
        except Exception as e:
            logger.error(f"Failed to retrieve BP case prep: {str(e)}")
            raise
