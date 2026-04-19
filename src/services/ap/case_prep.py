"""
Asian Parliamentary (AP) Case Prep Service.

Business logic layer for case preparation workflow.

Responsibilities:
1. Verify user is a participant in the match
2. Create empty CasePrep record
3. Call Prep Coach AI agent (role-specific context)
4. Validate AI-generated response
5. Persist case prep data to database
6. Generate embeddings for semantic search
7. Log AI call for observability

This service sits between routes and repository.
"""

import logging
import json
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from src.repositories.ap.case_prep import APCasePrepRepository
from src.ai.agents.prep_coach import generate_case_prep
from src.schemas.ap.case_prep import (
    CasePrepResponse,
    GenerateCasePrepRequest,
)

logger = logging.getLogger(__name__)


class APCasePrepService:
    """
    Service for AP case prep operations.
    
    Orchestrates the complete case prep workflow:
    AI agent → validation → persistence → embeddings → logging
    """
    
    def __init__(self):
        """Initialize service with repository."""
        self.repository = APCasePrepRepository()
    
    # GENERATE CASE PREP
        
    async def generate_case_prep(
        self,
        db: Session,
        user_id: str,
        match_id: str,
        request: GenerateCasePrepRequest
    ) -> CasePrepResponse:
        """
        Generate role-specific case prep for user in match.
        
        Complete Workflow:
        1. Create empty CasePrep record
        2. Call Prep Coach agent (role-specific)
        3. Validate AI response
        4. Update CasePrep with generated data
        5. Generate embeddings (for semantic search)
        6. Log AI call (for observability)
        7. Return formatted response
        
        Business Rules:
        - User must be authenticated
        - Only one case prep per user per match
        - Case prep is role-specific (first_speaker, second_speaker, whip)
        
        Args:
            db (Session): Database session
            user_id (str): UUID of user generating case prep
            match_id (str): UUID of match
            request (GenerateCasePrepRequest): Motion, side, and role
        
        Returns:
            CasePrepResponse: Generated case prep with all guidance
        
        Raises:
            ValueError: If invalid state or AI generation fails
            Exception: If database operation fails
        """
        try:
            logger.info(f"Generating case prep for user {user_id} in match {match_id}")
            
            # Extract side and role from request
            user_side = request.side
            user_role = request.role
            
            logger.info(f"User {user_id} role: {user_role} on {user_side} side")
            # Fetch existing empty CasePrep record created by MatchService
            case_prep_db = self.repository.get_case_prep_by_user_match(
                db=db,
                user_id=user_id,
                match_id=match_id
            )
            
            if not case_prep_db:
                raise ValueError("CasePrep initialization failed or match not found")
            
            ai_response = await generate_case_prep(
                motion_text=request.motion,
                side=user_side,
                format="asian_parliamentary"
            )
            
            # Validate AI response structure
            if not isinstance(ai_response, dict):
                raise ValueError("AI response must be a dictionary")
            
            required_fields = {"model_definition", "arguments", "counter_arguments", "evidence"}
            missing = required_fields - set(ai_response.keys())
            if missing:
                raise ValueError(f"AI response missing required fields: {missing}")
            
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
            # Extracts text from arguments, counter_arguments, evidence
            # and creates searchable vectors stored in PostgreSQL (pgvector)
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
            
            # Save embeddings to PostgreSQL via repository WITH metadata
            if embedding_texts:
                self.repository.save_embeddings(
                    db=db,
                    case_prep_id=str(case_prep_db.id),
                    match_id=match_id,
                    user_id=user_id,
                    side=user_side,
                    role=user_role,
                    motion_category="parliamentary_motion",
                    embedding_texts=embedding_texts
                )
            
            #Log AI call for observability
            self.repository.save_ai_call_log(
                db=db,
                match_id=match_id,
                agent_name="prep_coach",
                prompt_used=json.dumps({
                    "motion": request.motion,
                    "side": user_side,
                    "role": user_role,
                    "format": "asian_parliamentary"
                }),
                model_version="gpt-4o-mini",
                temperature=0.7,
                raw_output=json.dumps(ai_response, indent=2)
            )
            
            logger.info(f"Case prep generated: {case_prep_db.id}")
            
            return CasePrepResponse(
                id=str(case_prep_db.id),
                user_id=str(case_prep_db.user_id),
                match_id=match_id,
                side=user_side.lower(),
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
            logger.error(f"Failed to generate case prep: {str(e)}")
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
        Get case prep for current user in a match.
        
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
            session = db.query(DebateSession).filter(DebateSession.id == match_id).first()
            if not session:
                return None
            
            return CasePrepResponse(
                id=str(case_prep_db.id),
                user_id=str(case_prep_db.user_id),
                match_id=match_id,
                side=case_prep_db.side.lower(),
                role=session.human_role,
                model_definition=case_prep_db.model_definition or "",
                arguments=case_prep_db.arguments or [],
                counter_arguments=case_prep_db.counter_arguments or [],
                evidence=case_prep_db.evidence or []
            )
            
        except Exception as e:
            logger.error(f"Failed to retrieve case prep: {str(e)}")
            raise
