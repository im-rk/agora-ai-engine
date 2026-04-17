"""
Asian Parliamentary (AP) Match Repository.

Database layer for match persistence and queries.

Responsibilities:
- Create new AP matches
- Retrieve matches by ID
- List matches with filtering
- Update match status
- Delete/cancel matches
- Query helper methods

Database Model: Match (generic, but used here for AP format)
Columns: id, user_id, format, title, motion, status, government_team, opposition_team,
         speeches_completed, current_speaker_index, config, created_at, started_at,
         ended_at, updated_at

Note: AP-specific data (roles, speakers) are stored in nested JSON in config/metadata.
"""

import logging
import json
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from src.models.debate import Match
from src.schemas.ap.matches import (
    CreateMatchRequest,
    MatchResponse,
    MatchListItem,
    MatchStatus,
)

logger = logging.getLogger(__name__)


class APMatchRepository:
    """
    Repository for Asian Parliamentary match database operations.
    
    Handles all CRUD operations for AP matches with format-specific logic.
    """
    
    # ========================================================================
    # CREATE
    # ========================================================================
    
    @staticmethod
    def create_match(
        db: Session,
        user_id: str,
        request: CreateMatchRequest
    ) -> Match:
        """
        Create a new AP match in database.
        
        Flow:
        1. Validate request (already done by Pydantic)
        2. Create Match record with PENDING status
        3. Store government/opposition teams and speakers
        4. Store optional config (tournament, judge, round)
        
        Args:
            db (Session): Database session
            user_id (str): UUID of user creating match
            request (CreateMatchRequest): Match creation details
        
        Returns:
            Match: Created match object with ID
        
        Raises:
            SQLAlchemyError: If database operation fails
        
        Side Effects:
            - Creates new Match record in database
            - Initializes speeches_completed to 0
            - Sets status to "pending"
        """
        try:
            # Build government team data
            government_team = {
                "side": "government",
                "speakers": [
                    {
                        "user_id": speaker.user_id,
                        "role": speaker.role.value,
                        "spoke": False,
                        "speech_duration": None,
                        "poi_made": None,
                        "poi_received": None
                    }
                    for speaker in request.government
                ]
            }
            
            # Build opposition team data
            opposition_team = {
                "side": "opposition",
                "speakers": [
                    {
                        "user_id": speaker.user_id,
                        "role": speaker.role.value,
                        "spoke": False,
                        "speech_duration": None,
                        "poi_made": None,
                        "poi_received": None
                    }
                    for speaker in request.opposition
                ]
            }
            
            # Store config (tournament, judge, round)
            config = {
                "format": "asian_parliamentary",
                "adjudicator_id": request.config.adjudicator_id if request.config else None,
                "tournament_id": request.config.tournament_id if request.config else None,
                "round_number": request.config.round_number if request.config else None,
            }
            
            # Create match record
            match = Match(
                created_by=user_id,
                format="ap",
                title=request.title,
                motion=request.motion,
                status="pending",
                government_team=json.dumps(government_team),
                opposition_team=json.dumps(opposition_team),
                speeches_completed=0,
                current_speaker_index=None,
                config=json.dumps(config),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(match)
            db.commit()
            db.refresh(match)
            
            logger.info(f"AP match created: {match.id} by user {user_id}")
            return match
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create AP match: {str(e)}")
            raise
    
    # ========================================================================
    # READ
    # ========================================================================
    
    @staticmethod
    def get_match_by_id(db: Session, match_id: str) -> Optional[Match]:
        """
        Get match by ID.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
        
        Returns:
            Optional[Match]: Match if found, None otherwise
        """
        return db.query(Match).filter(
            Match.id == match_id,
            Match.format == "asian_parliamentary"
        ).first()
    
    @staticmethod
    def get_matches_for_user(
        db: Session,
        user_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
        sort_by: str = "created_at",
        order: str = "desc"
    ) -> tuple[List[Match], int]:
        """
        Get paginated list of user's AP matches with optional filtering.
        
        Query Strategy:
        - Filter by user_id (creator or participant)
        - Filter by format (AP only)
        - Filter by status if provided
        - Sort and paginate results
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
            status (Optional[str]): Filter by status (pending/in_progress/completed/cancelled)
            skip (int): Pagination offset
            limit (int): Results per page
            sort_by (str): Sort field (created_at, started_at)
            order (str): Sort order (asc, desc)
        
        Returns:
            tuple[List[Match], int]: (matches, total_count)
        """
        # Base query - matches for user in AP format
        query = db.query(Match).filter(
            Match.format == "asian_parliamentary",
            or_(
                Match.created_by == user_id,
                # Could also check if user is in participants (if needed)
            )
        )
        
        # Filter by status if provided
        if status:
            query = query.filter(Match.status == status)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        sort_field = getattr(Match, sort_by, Match.created_at)
        if order == "asc":
            query = query.order_by(sort_field)
        else:
            query = query.order_by(desc(sort_field))
        
        # Apply pagination
        matches = query.offset(skip).limit(limit).all()
        
        logger.info(f"Retrieved {len(matches)} AP matches for user {user_id}")
        return matches, total
    
    # ========================================================================
    # UPDATE
    # ========================================================================
    
    @staticmethod
    def update_match_status(
        db: Session,
        match_id: str,
        new_status: str,
        reason: Optional[str] = None
    ) -> Optional[Match]:
        """
        Update match status with validation.
        
        Allowed transitions:
        - pending → in_progress (first speech recorded)
        - in_progress → completed (judging submitted)
        - any → cancelled (at any time)
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            new_status (str): New status value
            reason (Optional[str]): Reason for status change
        
        Returns:
            Optional[Match]: Updated match if successful, None otherwise
        
        Side Effects:
            - Updates match status
            - Sets started_at if transitioning to in_progress
            - Sets ended_at if transitioning to completed/cancelled
        """
        try:
            match = APMatchRepository.get_match_by_id(db, match_id)
            if not match:
                logger.warning(f"Match not found: {match_id}")
                return None
            
            old_status = match.status
            match.status = new_status
            match.updated_at = datetime.utcnow()
            
            # Set timestamps based on transition
            if new_status == MatchStatus.IN_PROGRESS.value and not match.started_at:
                match.started_at = datetime.utcnow()
            elif new_status in [MatchStatus.COMPLETED.value, MatchStatus.CANCELLED.value]:
                match.ended_at = datetime.utcnow()
            
            db.commit()
            db.refresh(match)
            
            logger.info(f"Match {match_id} status: {old_status} → {new_status}")
            return match
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update match status: {str(e)}")
            raise
    
    @staticmethod
    def update_speeches_count(
        db: Session,
        match_id: str,
        new_count: int,
        current_speaker_index: Optional[int] = None
    ) -> Optional[Match]:
        """
        Update speeches completed count.
        
        Called when a speech is recorded to track debate progression.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            new_count (int): New speeches completed count (0-6)
            current_speaker_index (Optional[int]): Index of current speaker (0-5)
        
        Returns:
            Optional[Match]: Updated match
        """
        try:
            match = APMatchRepository.get_match_by_id(db, match_id)
            if not match:
                return None
            
            match.speeches_completed = new_count
            if current_speaker_index is not None:
                match.current_speaker_index = current_speaker_index
            match.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(match)
            
            return match
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update speeches count: {str(e)}")
            raise
    
    # ========================================================================
    # DELETE
    # ========================================================================
    
    @staticmethod
    def cancel_match(
        db: Session,
        match_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Cancel/delete a match.
        
        Soft delete: sets status to "cancelled" instead of removing.
        This preserves match history in database.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            reason (Optional[str]): Cancellation reason
        
        Returns:
            bool: True if cancelled successfully, False otherwise
        """
        try:
            match = APMatchRepository.get_match_by_id(db, match_id)
            if not match:
                logger.warning(f"Match not found for cancellation: {match_id}")
                return False
            
            match.status = MatchStatus.CANCELLED.value
            match.ended_at = datetime.utcnow()
            match.updated_at = datetime.utcnow()
            
            # Store cancellation reason if provided
            if reason:
                if not match.config:
                    match.config = {}
                match.config["cancellation_reason"] = reason
            
            db.commit()
            
            logger.info(f"Match cancelled: {match_id} - Reason: {reason or 'Not specified'}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to cancel match: {str(e)}")
            raise
    
    # ========================================================================
    # QUERY HELPERS
    # ========================================================================
    
    @staticmethod
    def get_match_by_speaker(
        db: Session,
        user_id: str,
        status: Optional[str] = None
    ) -> List[Match]:
        """
        Get all AP matches where user is a participant/speaker.
        
        This is a convenience method to find all matches a user participated in.
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
            status (Optional[str]): Optional status filter
        
        Returns:
            List[Match]: Matches where user is a speaker
        """
        # Query for matches where user appears in speakers
        query = db.query(Match).filter(
            Match.format == "asian_parliamentary",
            Match.government_team.contains(user_id) | Match.opposition_team.contains(user_id)
        )
        
        if status:
            query = query.filter(Match.status == status)
        
        return query.all()
    
    @staticmethod
    def get_completed_matches(
        db: Session,
        skip: int = 0,
        limit: int = 10
    ) -> tuple[List[Match], int]:
        """
        Get all completed AP matches (for statistics, leaderboards, etc.).
        
        Args:
            db (Session): Database session
            skip (int): Pagination offset
            limit (int): Results per page
        
        Returns:
            tuple[List[Match], int]: (completed_matches, total_count)
        """
        query = db.query(Match).filter(
            Match.format == "asian_parliamentary",
            Match.status == MatchStatus.COMPLETED.value
        ).order_by(desc(Match.ended_at))
        
        total = query.count()
        matches = query.offset(skip).limit(limit).all()
        
        return matches, total
