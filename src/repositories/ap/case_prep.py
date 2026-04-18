"""
Asian Parliamentary (AP) Case Prep Repository.

Database layer for case prep persistence and queries.

Responsibilities:
- Create empty case prep records (filled by Prep Coach agent later)
- Retrieve case prep by ID
- Retrieve case prep by user + match (current user's case prep)
- Update case prep with AI-generated data
- Log AI calls for observability

Database Model: CasePrep (adapted for AP format)
Columns: id, user_id, match_id, side, role, model_definition, arguments,
         counter_arguments, evidence, role_brief, tips, created_at, updated_at

Note: AP-specific data stored as JSON/JSONB for flexibility.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.models.setup import CasePrep, AICallLog, ArgumentEmbedding
from src.services.embedding_service import get_embedding

logger = logging.getLogger(__name__)


class APCasePrepRepository:
    """
    Repository for AP case prep database operations.
    
    Handles all CRUD operations for case prep with role-specific context.
    """
    
    # CREATE
    
    @staticmethod
    def create_case_prep(
        db: Session,
        user_id: str,
        motion_id: str,
        side: str
    ) -> CasePrep:
        """
        Create empty case prep container (filled by Prep Coach agent later).
        
        Flow:
        1. Create CasePrep record with user_id, motion_id, side
        2. Initialize with NULL AI-generated fields
        3. Return record ID for later update
        
        Args:
            db (Session): Database session
            user_id (str): UUID of user creating case prep
            motion_id (str): UUID of motion this is for
            side (str): "government" or "opposition"
        
        Returns:
            CasePrep: Empty case prep record (waiting for AI generation)
        
        Raises:
            SQLAlchemyError: If database operation fails
        
        Side Effects:
            - Creates new CasePrep record
            - Initializes all AI fields to None
        """
        try:
            new_prep = CasePrep(
                user_id=user_id,
                motion_id=motion_id,
                side=side
            )
            
            db.add(new_prep)
            db.flush()
            
            logger.info(f"Case prep created: {new_prep.id} for user {user_id}, motion {motion_id}, side {side}")
            return new_prep
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create case prep: {str(e)}")
            raise
    
    # READ
    
    @staticmethod
    def get_case_prep_by_id(
        db: Session,
        prep_id: str
    ) -> Optional[CasePrep]:
        """
        Fetch case prep record by ID.
        
        Args:
            db (Session): Database session
            prep_id (str): Case prep UUID
        
        Returns:
            Optional[CasePrep]: Case prep if found, None otherwise
        """
        try:
            return db.query(CasePrep).filter(CasePrep.id == prep_id).first()
        except Exception as e:
            logger.error(f"Failed to fetch case prep by ID: {str(e)}")
            raise
    
    @staticmethod
    def get_case_prep_by_user_match(
        db: Session,
        user_id: str,
        match_id: str
    ) -> Optional[CasePrep]:
        """
        Fetch case prep for a specific user + match (their case prep).
        
        Follows resource hierarchy: Match → User's Case Prep
        Used to get current user's case prep within a match context.
        """
        try:
            from src.models.debate import DebateSession
            match = db.query(DebateSession).filter(
                DebateSession.id == match_id,
                DebateSession.user_id == user_id
            ).first()
            
            if not match or not match.case_prep_id:
                return None
                
            return db.query(CasePrep).filter(CasePrep.id == match.case_prep_id).first()
        except Exception as e:
            logger.error(f"Failed to fetch case prep by user+match: {str(e)}")
            raise
    
    # UPDATE
    
    @staticmethod
    def update_case_prep(
        db: Session,
        case_prep_id: str,
        model_definition: str,
        arguments: List[Dict[str, Any]],
        counter_arguments: List[str],
        evidence: List[str],
        role_brief: Optional[Dict[str, Any]] = None,
        tips: Optional[List[str]] = None
    ) -> CasePrep:
        """
        Save AI-generated case prep data to database.
        
        Called after Prep Coach agent generates case prep.
        Updates empty record with structured AI output.
        
        Args:
            db (Session): Database session
            case_prep_id (str): Case prep UUID to update
            model_definition (str): Case theory/interpretation
            arguments (List[Dict]): Main arguments for the role
            counter_arguments (List[str]): Expected opposing arguments
            evidence (List[str]): Supporting facts
            role_brief (Optional[Dict]): Role-specific briefing
            tips (Optional[List]): Role-specific tips
        
        Returns:
            CasePrep: Updated case prep record
        
        Raises:
            ValueError: If case prep not found
            SQLAlchemyError: If database operation fails
        """
        try:
            case_prep = db.query(CasePrep).filter(CasePrep.id == case_prep_id).first()
            
            if not case_prep:
                raise ValueError(f"CasePrep with id {case_prep_id} not found")
            
            # Update all AI-generated fields
            case_prep.model_definition = model_definition
            case_prep.arguments = arguments
            case_prep.counter_arguments = counter_arguments
            case_prep.evidence = evidence
            case_prep.role_brief = role_brief or {}
            case_prep.tips = tips or []
            case_prep.updated_at = datetime.now(timezone.utc)
            
            db.add(case_prep)
            db.commit()
            db.refresh(case_prep)
            
            logger.info(f"Case prep updated: {case_prep_id}")
            return case_prep
            
        except ValueError:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update case prep: {str(e)}")
            raise
    
    # LOGGING
    
    @staticmethod
    def save_ai_call_log(
        db: Session,
        match_id: str,
        agent_name: str,
        prompt_used: str,
        model_version: str,
        temperature: float,
        raw_output: str
    ) -> AICallLog:
        """
        Log AI agent call for observability (Langfuse).
        
        Called after Prep Coach generates case prep.
        Stores prompt, parameters, and output for debugging/observability.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID (for context)
            agent_name (str): Name of AI agent ("prep_coach")
            prompt_used (str): Prompt sent to AI
            model_version (str): LLM model used (e.g., "gpt-4")
            temperature (float): Temperature parameter
            raw_output (str): Raw response from AI
        
        Returns:
            AICallLog: Created log record
        
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            ai_log = AICallLog(
                session_id=match_id,  # Reuse match_id as session context
                agent_name=agent_name,
                prompt_used=prompt_used,
                model_version=model_version,
                temperature=temperature,
                raw_output=raw_output
            )
            
            db.add(ai_log)
            db.commit()
            db.refresh(ai_log)
            
            logger.info(f"AI call logged: {agent_name} for match {match_id}")
            return ai_log
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save AI call log: {str(e)}")
            raise
    
    # EMBEDDINGS
    
    @staticmethod
    def save_embeddings(
        db: Session,
        case_prep_id: str,
        embedding_texts: List[Tuple[str, str]]
    ) -> int:
        """
        Generate and store vector embeddings for semantic search.
        
        Converts text content (arguments, counter-arguments, evidence) into
        vector embeddings and persists them to PostgreSQL pgvector column.
        
        Used for semantic search: finding similar arguments across all case preps.
        
        Args:
            db (Session): Database session
            case_prep_id (str): UUID of case prep being embedded
            embedding_texts (List[Tuple[str, str]]): List of (content, type) tuples
                - content: Text to embed
                - type: "argument_claim", "argument_reasoning", "counter_argument", "evidence"
        
        Returns:
            int: Number of embeddings successfully stored
        
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            stored_count = 0
            
            for content, arg_type in embedding_texts:
                try:
                    # Generate vector embedding from text
                    embedding_vector = get_embedding(content)
                    
                    # Create embedding record
                    embedding_record = ArgumentEmbedding(
                        case_prep_id=case_prep_id,
                        content=content,
                        embedding=embedding_vector,
                        argument_type=arg_type
                    )
                    
                    db.add(embedding_record)
                    stored_count += 1
                    
                except Exception as e:
                    logger.warning(f"Embedding generation failed for: {content[:50]}... ({str(e)})")
                    # Continue with next embedding, don't fail entire operation
                    continue
            
            db.commit()
            logger.info(f"Stored {stored_count} embeddings for case prep {case_prep_id}")
            return stored_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save embeddings: {str(e)}")
            raise
