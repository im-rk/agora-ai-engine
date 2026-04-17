"""
Asian Parliamentary (AP) Match Service.

Business logic layer for match operations.

Responsibilities:
- Orchestrate match creation workflow
- Validate business rules
- Handle match state transitions
- Prepare data for API responses
- Interact with repositories

This service sits between API routes and repository.
It enforces business logic without knowing about HTTP details.
"""

import logging
import json
from typing import Optional, Tuple, List
from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.ap.matches import APMatchRepository
from src.schemas.ap.matches import (
    CreateMatchRequest,
    MatchResponse,
    MatchListResponse,
    MatchListItem,
    MatchStatus,
    APRole,
    DebateSide,
    TeamInfo,
    SpeakerInfo,
    NextSpeaker,
)
from src.models.debate import Match

logger = logging.getLogger(__name__)


class APMatchService:
    """
    Service layer for AP match operations.
    
    Encapsulates business logic for:
    - Creating matches with validation
    - Listing and retrieving matches
    - Managing match state transitions
    - Building API responses
    """
    
    def __init__(self):
        """Initialize service with repository."""
        self.repository = APMatchRepository()
    
    # CREATE  
      
    async def create_match(
        self,
        db: Session,
        user_id: str,
        request: CreateMatchRequest
    ) -> MatchResponse:
        """
        Create a new AP match with full validation.
        
        Business Rules:
        1. User must provide all 6 speakers (3 per side)
        2. Each side must have exactly one first_speaker, second_speaker, whip
        3. All speakers must be different users
        4. Match starts in PENDING status
        
        Args:
            db (Session): Database session
            user_id (str): UUID of user creating match
            request (CreateMatchRequest): Match creation request
        
        Returns:
            MatchResponse: Created match details
        
        Raises:
            ValueError: If business rules violated
        """
        try:
            # Validate no duplicate speakers
            all_speakers = [s.user_id for s in request.government] + [s.user_id for s in request.opposition]
            if len(all_speakers) != len(set(all_speakers)):
                raise ValueError("All speakers must be unique users")
            
            # Create in database
            match_db = self.repository.create_match(db, user_id, request)
            
            logger.info(f"Match service created match: {match_db.id}")
            
            # Convert to response
            return self._build_match_response(match_db)
            
        except ValueError as e:
            logger.warning(f"Validation error creating match: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to create match: {str(e)}")
            raise
    
    # READ
    
    async def get_match(
        self,
        db: Session,
        match_id: str
    ) -> Optional[MatchResponse]:
        """
        Get match by ID with full details.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
        
        Returns:
            Optional[MatchResponse]: Match if found, None otherwise
        """
        match_db = self.repository.get_match_by_id(db, match_id)
        if not match_db:
            logger.info(f"Match not found: {match_id}")
            return None
        
        return self._build_match_response(match_db)
    
    async def list_matches(
        self,
        db: Session,
        user_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 10,
        sort_by: str = "created_at",
        order: str = "desc"
    ) -> MatchListResponse:
        """
        Get paginated list of user's AP matches.
        
        Filtering & Sorting:
        - Filter by status: pending, in_progress, completed, cancelled
        - Sort by: created_at, started_at
        - Order: asc, desc
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
            status (Optional[str]): Status filter
            skip (int): Pagination offset
            limit (int): Results per page
            sort_by (str): Sort field
            order (str): Sort order
        
        Returns:
            MatchListResponse: Paginated matches
        """
        try:
            # Validate inputs
            if limit > 100:
                limit = 100
            if skip < 0:
                skip = 0
            
            # Get from repository
            matches_db, total = self.repository.get_matches_for_user(
                db, user_id, status, skip, limit, sort_by, order
            )
            
            # Convert to response items
            items = [
                MatchListItem(
                    id=m.id,
                    title=m.title,
                    status=m.status,
                    motion=m.motion[:100] + "..." if len(m.motion) > 100 else m.motion,
                    speeches_completed=m.speeches_completed,
                    government_side="Government",
                    opposition_side="Opposition",
                    created_at=m.created_at,
                    started_at=m.started_at
                )
                for m in matches_db
            ]
            
            return MatchListResponse(
                matches=items,
                total=total,
                skip=skip,
                limit=limit
            )
            
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
        Update match status with state validation.
        
        State Machine:
        - pending  → in_progress (automatic on first speech)
        - pending  → cancelled (manual)
        - in_progress → completed (when judging submitted)
        - in_progress → cancelled (manual)
        - completed → (no transitions)
        - cancelled → (terminal state)
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            new_status (str): New status
            reason (Optional[str]): Reason for change
        
        Returns:
            Optional[MatchResponse]: Updated match or None
        
        Raises:
            ValueError: If transition not allowed
        """
        try:
            # Get current match
            match_db = self.repository.get_match_by_id(db, match_id)
            if not match_db:
                return None
            
            # Validate state transition
            old_status = match_db.status
            if not self._is_valid_transition(old_status, new_status):
                raise ValueError(f"Invalid status transition: {old_status} → {new_status}")
            
            # Update in repository
            match_db = self.repository.update_match_status(
                db, match_id, new_status, reason
            )
            
            logger.info(f"Match status updated: {match_id} - {old_status} → {new_status}")
            
            return self._build_match_response(match_db)
            
        except ValueError as e:
            logger.warning(f"Status transition error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to update match status: {str(e)}")
            raise
    
    # DELETE
    
    async def cancel_match(
        self,
        db: Session,
        match_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Cancel a match.
        
        Allows cancellation at any stage:
        - pending: Before debate starts
        - in_progress: During debate
        - cancellation is a terminal state
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            reason (Optional[str]): Cancellation reason
        
        Returns:
            bool: True if cancelled successfully
        """
        try:
            success = self.repository.cancel_match(db, match_id, reason)
            
            if success:
                logger.info(f"Match cancelled: {match_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cancel match: {str(e)}")
            raise
    
    # HELPER METHODS - Response Building
    
    def _build_match_response(self, match_db: Match) -> MatchResponse:
        """
        Convert database match to API response format.
        
        Handles:
        - Extracting team/speaker data from nested JSON
        - Calculating next speaker
        - Formatting timestamps
        - Building all response sub-objects
        
        Args:
            match_db (Match): Database match object
        
        Returns:
            MatchResponse: Formatted API response
        """
        # Deserialize team data from JSON
        government_data = json.loads(match_db.government_team) if match_db.government_team else {"speakers": []}
        opposition_data = json.loads(match_db.opposition_team) if match_db.opposition_team else {"speakers": []}
        config_data = json.loads(match_db.config) if match_db.config else {}
        
        # Build government team
        government = TeamInfo(
            team_id=f"gov_{str(match_db.id)[:8]}",
            side=DebateSide.GOVERNMENT,
            speakers=[
                SpeakerInfo(
                    user_id=s["user_id"],
                    role=s["role"],  # Pydantic auto-converts string to APRole enum
                    name=s.get("name", s["user_id"][:8]),
                    spoke=s.get("spoke", False),
                    speech_duration=s.get("speech_duration"),
                    poi_made=s.get("poi_made"),
                    poi_received=s.get("poi_received")
                )
                for s in government_data.get("speakers", [])
            ]
        )
        
        # Build opposition team
        opposition = TeamInfo(
            team_id=f"opp_{str(match_db.id)[:8]}",
            side=DebateSide.OPPOSITION,
            speakers=[
                SpeakerInfo(
                    user_id=s["user_id"],
                    role=s["role"],  # Pydantic auto-converts string to APRole enum
                    name=s.get("name", s["user_id"][:8]),
                    spoke=s.get("spoke", False),
                    speech_duration=s.get("speech_duration"),
                    poi_made=s.get("poi_made"),
                    poi_received=s.get("poi_received")
                )
                for s in opposition_data.get("speakers", [])
            ]
        )
        
        # Calculate next speaker
        next_speaker = None
        if match_db.current_speaker_index is not None and match_db.current_speaker_index < 5:
            next_speaker = self._get_next_speaker(
                match_db.current_speaker_index,
                government,
                opposition
            )
        
        # Build response
        return MatchResponse(
            id=str(match_db.id),
            title=match_db.title,
            motion=match_db.motion,
            format="asian_parliamentary",
            status=match_db.status,
            government=government,
            opposition=opposition,
            speeches_completed=match_db.speeches_completed or 0,
            current_speaker_index=match_db.current_speaker_index,
            next_speaker=next_speaker,
            adjudicator_id=config_data.get("adjudicator_id"),
            tournament_id=config_data.get("tournament_id"),
            round_number=config_data.get("round_number"),
            created_at=match_db.created_at,
            created_by=str(match_db.created_by),
            started_at=match_db.started_at,
            ended_at=match_db.ended_at,
            updated_at=match_db.updated_at
        )
    
    def _get_next_speaker(
        self,
        current_index: int,
        government: TeamInfo,
        opposition: TeamInfo
    ) -> Optional[NextSpeaker]:
        """
        Calculate next speaker based on AP speech order.
        
        AP Speech Order (alternating government/opposition):
        0: Government First Speaker
        1: Opposition First Speaker
        2: Government Second Speaker
        3: Opposition Second Speaker
        4: Government Whip
        5: Opposition Whip
        
        Args:
            current_index (int): Current speech index (0-5)
            government (TeamInfo): Government team
            opposition (TeamInfo): Opposition team
        
        Returns:
            Optional[NextSpeaker]: Next speaker info or None if at end
        """
        if current_index >= 5:
            return None
        
        # AP speech order mapping
        order = [
            ("government", "first_speaker"),
            ("opposition", "first_speaker"),
            ("government", "second_speaker"),
            ("opposition", "second_speaker"),
            ("government", "whip"),
            ("opposition", "whip"),
        ]
        
        next_index = current_index + 1
        side_str, role_str = order[next_index]
        
        # Get next speaker info
        team = government if side_str == "government" else opposition
        for speaker in team.speakers:
            if speaker.role.value == role_str:
                return NextSpeaker(
                    role=speaker.role,
                    side=team.side,
                    user_id=speaker.user_id,
                    order_position=next_index + 1  # 1-indexed for display
                )
        
        return None
    
    # HELPER METHODS - Validation
    
    @staticmethod
    def _is_valid_transition(old_status: str, new_status: str) -> bool:
        """
        Validate state transition rules.
        
        Allowed transitions:
        - pending → in_progress, cancelled
        - in_progress → completed, cancelled
        - completed → (terminal)
        - cancelled → (terminal)
        
        Args:
            old_status (str): Current status
            new_status (str): Desired status
        
        Returns:
            bool: True if transition allowed
        """
        transitions = {
            MatchStatus.PENDING.value: [
                MatchStatus.IN_PROGRESS.value,
                MatchStatus.CANCELLED.value
            ],
            MatchStatus.IN_PROGRESS.value: [
                MatchStatus.COMPLETED.value,
                MatchStatus.CANCELLED.value
            ],
            MatchStatus.COMPLETED.value: [],
            MatchStatus.CANCELLED.value: [],
        }
        
        return new_status in transitions.get(old_status, [])
