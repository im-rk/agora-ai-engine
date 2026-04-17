"""
Asian Parliamentary (AP) Match Service.

Business logic layer for AP match operations.

Orchestrates match lifecycle following same pattern as match_service.py:
1. Create Motion (debate topic)
2. Create DebateSession (the match)
3. Create CasePrep (user's prepared case)
4. Initialize Redis state
5. Generate case prep via AI

Responsibilities:
- Create new matches (single user initiating)
- Handle match lifecycle (status transitions)
- Persist to database via repository
- Trigger AI case prep generation
"""

import logging
import json
from typing import Optional, List
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.repositories.ap.matches import APMatchRepository
from src.services.ap.case_prep import APCasePrepService
from src.models.debate import DebateSession, MatchFormat, MatchStatus as DBMatchStatus
from src.schemas.ap.matches import (
    CreateMatchRequest,
    MatchResponse,
    MatchListItem,
    MatchStatus,
    APRole,
    DebateSide,
)
from src.engine.state import state_manager

logger = logging.getLogger(__name__)


class APMatchService:
    """
    Service layer for AP match operations.
    
    Orchestrates:
    - Match creation with Motion, DebateSession, CasePrep
    - Redis state initialization
    - Match status transitions
    - Case prep generation
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
        1. Create Motion record (debate topic)
        2. Create CasePrep record (user's prepared case)
        3. Create DebateSession record (the match)
        4. Initialize Redis state (all 6 speakers scheduled)
        5. Publish START_MATCH event to Redis PubSub
        6. Generate case prep for this user
        
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
            logger.info(f"Creating AP match for user {user_id}: {request.motion[:50]}...")
            
            # STEP 1-3: Create match in database (Motion + CasePrep + DebateSession)
            match_db = self.repository.create_match(
                db=db,
                user_id=user_id,
                motion=request.motion,
                side=request.side.value,  # enum to string
                role=request.role.value,   # enum to string
                skill_level="BEGINNER"     # Default for now
            )
            
            match_id = str(match_db.id)
            logger.info(f"Match created: {match_id}")
            logger.info(f"  Motion ID: {match_db.motion_id}")
            logger.info(f"  CasePrep ID: {match_db.case_prep_id}")
            
            # STEP 4: Initialize Redis state (all 6 speakers scheduled)
            await state_manager.initialize_match(
                match_id=match_id,
                human_side=request.side.value,
                format_type="AP",
                preferred_role=request.role.value
            )
            logger.info(f"Redis state initialized for match {match_id}")
            
            # STEP 5: Publish START_MATCH event to trigger Python consumer
            import redis.asyncio as redis
            from src.core.config import settings
            
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_client.publish(
                f"debate:{match_id}:events",
                json.dumps({"action": "START_MATCH", "match_id": match_id})
            )
            logger.info(f"Published START_MATCH event for {match_id}")
            
            # STEP 6: Generate case prep for user via AI
            from src.schemas.ap.case_prep import GenerateCasePrepRequest
            case_prep_request = GenerateCasePrepRequest(
                motion=request.motion,
                side=request.side,
                role=request.role
            )
            case_prep = await self.case_prep_service.generate_case_prep(
                db=db,
                user_id=user_id,
                match_id=match_id,
                request=case_prep_request
            )
            logger.info(f"Case prep generated for user {user_id} in match {match_id}")
            
            # Build response
            return self._build_match_response(match_db)
            
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
            
            return self._build_match_response(match_db)
            
        except Exception as e:
            logger.error(f"Failed to get match: {str(e)}")
            raise
    
    async def list_matches(
        self,
        db: Session,
        user_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
        sort_by: str = "created_at",
        order: str = "desc"
    ) -> dict:
        """
        List user's AP matches with pagination.
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
            status (Optional[str]): Filter by status (started, finished, aborted)
            skip (int): Pagination offset
            limit (int): Results per page
            sort_by (str): Field to sort by (created_at, started_at)
            order (str): Sort order (asc, desc)
        
        Returns:
            dict: {"matches": [...], "total": int, "skip": int, "limit": int}
        """
        try:
            if limit > 100:
                limit = 100
            if skip < 0:
                skip = 0
            
            # Get matches (sort_by and order parameters accepted but currently fixed to started_at desc in repository)
            matches_db = self.repository.get_matches_for_user(
                db, user_id, status, skip, limit
            )
            
            # Get total count for pagination
            count_query = db.query(func.count(DebateSession.id)).filter(
                DebateSession.user_id == user_id,
                DebateSession.format == MatchFormat.ASIAN_PARLIAMENTARY
            )
            
            if status:
                status_enum = DBMatchStatus[status.upper()]
                count_query = count_query.filter(DebateSession.status == status_enum)
            
            total = count_query.scalar() or 0
            
            items = [
                MatchListItem(
                    id=str(m.id),
                    motion=m.motion.motion_text[:100] + "..." if len(m.motion.motion_text) > 100 else m.motion.motion_text,
                    status=self._map_match_status(m.status),
                    your_role=APRole(m.human_role),
                    your_side=DebateSide(m.case_prep.side.lower()),
                    created_at=m.started_at,
                    started_at=m.started_at,
                    ended_at=m.ended_at
                )
                for m in matches_db
            ]
            
            return {
                "matches": items,
                "total": total,
                "skip": skip,
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"Failed to list matches: {str(e)}")
            raise
    
    # UPDATE    
    async def update_match_status(
        self,
        db: Session,
        match_id: str,
        new_status: str,
        reason: Optional[str] = None
    ) -> Optional[MatchResponse]:
        """
        Update match status.
        
        Valid statuses: started, finished, aborted
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            new_status (str): New status
            reason (Optional[str]): Reason for status change
        
        Returns:
            Optional[MatchResponse]: Updated match or None
        """
        try:
            match_db = self.repository.update_match_status(db, match_id, new_status)
            
            if not match_db:
                return None
            
            logger.info(f"Match status updated: {match_id} → {new_status}. Reason: {reason or 'Not specified'}")
            return self._build_match_response(match_db)
            
        except Exception as e:
            logger.error(f"Failed to update status: {str(e)}")
            raise
    
    # DELETE
    
    async def cancel_match(
        self,
        db: Session,
        match_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Cancel a match at any stage.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            reason (Optional[str]): Reason for cancellation
        
        Returns:
            bool: True if cancelled successfully
        """
        try:
            success = self.repository.cancel_match(db, match_id)
            
            if success:
                logger.info(f"Match cancelled: {match_id}. Reason: {reason or 'Not specified'}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cancel match: {str(e)}")
            raise
    
    # HELPERS
    
    def _build_match_response(self, match_db) -> MatchResponse:
        """Build MatchResponse from DebateSession database object."""
        try:
            # Get motion and case prep data
            motion = match_db.motion
            case_prep = match_db.case_prep
            
            return MatchResponse(
                match_id=str(match_db.id),
                motion=motion.motion_text if motion else "",
                status=self._map_match_status(match_db.status),
                created_by=str(match_db.user_id),
                your_role=APRole(match_db.human_role),
                your_side=DebateSide(case_prep.side.lower()),
                created_at=match_db.started_at,
                started_at=match_db.started_at,
                ended_at=match_db.ended_at,
                participants=[]  # TODO: Populate from debate participants table
            )
        except Exception as e:
            logger.error(f"Failed to build match response: {str(e)}")
            raise
    
    def _map_match_status(self, db_status) -> str:
        """
        Map database MatchStatus enum to schema MatchStatus.
        
        DB enums: STARTED, FINISHED, ABORTED
        Schema enums: awaiting_participants, debate_in_progress, judging_phase, completed, cancelled
        """
        status_map = {
            "STARTED": MatchStatus.DEBATE_IN_PROGRESS,
            "FINISHED": MatchStatus.COMPLETED,
            "ABORTED": MatchStatus.CANCELLED,
        }
        return status_map.get(db_status.name, MatchStatus.DEBATE_IN_PROGRESS)
