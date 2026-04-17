"""
Asian Parliamentary (AP) Match Service.

Business logic layer for match operations.

Responsibilities:
1. Create new match (single user initiating)
2. Initialize Redis state (all 6 speakers scheduled)
3. Generate case prep for the user
4. Handle match lifecycle (status transitions)
5. Persist to database via repository

Simple, focused flow without complex team management.
"""

import logging
import json
from typing import Optional, List
from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.ap.matches import APMatchRepository
from src.services.ap.case_prep import APCasePrepService
from src.schemas.ap.matches import (
    CreateMatchRequest,
    MatchResponse,
    MatchListItem,
    MatchStatus,
)
from src.engine.state import state_manager

logger = logging.getLogger(__name__)


class APMatchService:
    """
    Service layer for AP match operations.
    
    Orchestrates:
    - Match creation with case prep generation
    - Redis state initialization
    - Match status transitions
    """
    
    def __init__(self):
        """Initialize service with repository and dependencies."""
        self.repository = APMatchRepository()
        self.case_prep_service = APCasePrepService()
    
    # CREATE MATCH
    
    async def create_match(
        self,
        db: Session,
        user_id: str,
        request: CreateMatchRequest
    ) -> MatchResponse:
        """
        Create a new AP match and initialize everything.
        
        Flow:
        1. Create match record in database
        2. Initialize Redis state (all 6 speakers scheduled)
        3. Publish START_MATCH event to Redis PubSub
        4. Generate case prep for this user
        
        Args:
            db (Session): Database session
            user_id (str): User creating the match
            request (CreateMatchRequest): {motion, side, role}
        
        Returns:
            MatchResponse: Created match with status AWAITING_PARTICIPANTS
        
        Raises:
            ValueError: If validation fails
            Exception: If any step fails
        """
        try:
            logger.info(f"Creating AP match for user {user_id}")
            
            # STEP 1: Create match in database
            match_db = self.repository.create_match(
                db=db,
                user_id=user_id,
                motion=request.motion,
                side=request.side,
                role=request.role
            )
            db.commit()
            db.refresh(match_db)
            
            match_id = str(match_db.id)
            logger.info(f"Match created: {match_id}")
            
            # STEP 2: Initialize Redis state (all 6 speakers scheduled)
            await state_manager.initialize_match(
                match_id=match_id,
                human_side=request.side,
                format_type="AP",
                preferred_role=request.role
            )
            logger.info(f"Redis state initialized for match {match_id}")
            
            # STEP 3: Publish START_MATCH event to trigger Python consumer
            import redis.asyncio as redis
            from src.core.config import settings
            
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_client.publish(
                f"debate:{match_id}:events",
                json.dumps({"action": "START_MATCH", "match_id": match_id})
            )
            logger.info(f"Published START_MATCH event for {match_id}")
            
            # STEP 4: Generate case prep for user
            case_prep = await self.case_prep_service.generate_case_prep(
                db=db,
                user_id=user_id,
                match_id=match_id,
                request=request
            )
            logger.info(f"Case prep generated for user {user_id}")
            
            # Return response
            return MatchResponse.model_validate(match_db)
            
        except ValueError as e:
            logger.warning(f"Validation error: {str(e)}")
            db.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to create match: {str(e)}")
            db.rollback()
            raise
    
    # READ
    
    async def get_match(
        self,
        db: Session,
        match_id: str
    ) -> Optional[MatchResponse]:
        """
        Get match details by ID.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
        
        Returns:
            Optional[MatchResponse]: Match if found, None otherwise
        """
        try:
            match_db = self.repository.get_match_by_id(db, match_id)
            
            if not match_db:
                logger.info(f"Match not found: {match_id}")
                return None
            
            return MatchResponse.model_validate(match_db)
            
        except Exception as e:
            logger.error(f"Failed to get match: {str(e)}")
            raise
    
    async def list_matches(
        self,
        db: Session,
        user_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 10
    ) -> List[MatchListItem]:
        """
        List user's AP matches.
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
            status (Optional[str]): Filter by status
            skip (int): Pagination offset
            limit (int): Results per page
        
        Returns:
            List[MatchListItem]: User's matches
        """
        try:
            if limit > 100:
                limit = 100
            if skip < 0:
                skip = 0
            
            matches_db = self.repository.get_matches_for_user(
                db, user_id, status, skip, limit
            )
            
            items = [
                MatchListItem(
                    id=str(m.id),
                    motion=m.motion[:100] + "..." if len(m.motion) > 100 else m.motion,
                    status=m.status,
                    your_role=m.role,
                    your_side=m.side,
                    created_at=m.created_at,
                    started_at=m.started_at,
                    ended_at=m.ended_at
                )
                for m in matches_db
            ]
            
            return items
            
        except Exception as e:
            logger.error(f"Failed to list matches: {str(e)}")
            raise
    
    # UPDATE
    
    async def update_match_status(
        self,
        db: Session,
        match_id: str,
        new_status: str
    ) -> Optional[MatchResponse]:
        """
        Update match status.
        
        Go Gateway orchestrates the flow and determines valid transitions.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            new_status (str): New status
        
        Returns:
            Optional[MatchResponse]: Updated match or None
        """
        try:
            match_db = self.repository.get_match_by_id(db, match_id)
            if not match_db:
                return None
            
            # Update status (Go Gateway orchestrates the flow)
            match_db = self.repository.update_match_status(db, match_id, new_status)
            db.commit()
            db.refresh(match_db)
            
            logger.info(f"Match status updated: {match_id} → {new_status}")
            
            return MatchResponse.model_validate(match_db)
            
        except Exception as e:
            logger.error(f"Failed to update status: {str(e)}")
            db.rollback()
            raise
    
    # DELETE
    
    async def cancel_match(
        self,
        db: Session,
        match_id: str
    ) -> bool:
        """
        Cancel a match at any stage.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
        
        Returns:
            bool: True if cancelled successfully
        """
        try:
            success = self.repository.cancel_match(db, match_id)
            
            if success:
                db.commit()
                logger.info(f"Match cancelled: {match_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cancel match: {str(e)}")
            db.rollback()
            raise

