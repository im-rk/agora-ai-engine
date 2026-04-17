"""
Asian Parliamentary (AP) Match Repository.

Database layer for AP match persistence using DebateSession model.

Responsibilities:
- Create new AP matches (DebateSession + Motion + CasePrep)
- Retrieve matches by ID
- List matches with filtering
- Update match status
- Cancel/delete matches

Maps AP schemas to actual database models:
- Motion: Debate topic (shared with old system)
- CasePrep: User's prepared case for a side
- DebateSession: THE match record (format=AP)
"""

import logging
import uuid
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models.debate import DebateSession, MatchFormat, MatchStatus, Turn
from src.models.setup import Motion, MotionCategory, CasePrep
from src.models.user import SkillLevel

logger = logging.getLogger(__name__)


class APMatchRepository:
    """
    Repository for Asian Parliamentary match database operations.
    
    Uses DebateSession as the primary match model (same as old system).
    Creates Motion and CasePrep records as needed.
    """
    
    # CREATE
    
    @staticmethod
    def create_match(
        db: Session,
        user_id: str,
        motion: str,
        side: str,
        role: str,
        skill_level: str = "BEGINNER"
    ) -> DebateSession:
        """
        Create a new AP match.
        
        Flow:
        1. Create Motion record (debate topic)
        2. Create CasePrep record (user's prepared case)
        3. Create DebateSession record (the match)
        
        Args:
            db (Session): Database session
            user_id (str): UUID of user creating match
            motion (str): Debate motion text (e.g., "This house believes...")
            side (str): "government" or "opposition"
            role (str): AP role (e.g., "prime_minister")
            skill_level (str): User's skill level (BEGINNER, INTERMEDIATE, ADVANCED)
        
        Returns:
            DebateSession: Created debate session (the match)
        
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails
        """
        try:
            # Convert side to title case for database
            side_db = "Government" if side.lower() == "government" else "Opposition"
            
            # STEP 1: Create Motion record
            motion_obj = Motion(
                id=uuid.uuid4(),
                motion_text=motion,
                category=MotionCategory.CUSTOM,
                is_custom=True
            )
            db.add(motion_obj)
            db.flush()  # Get ID before next step
            
            logger.info(f"Motion created: {motion_obj.id}")
            
            # STEP 2: Create CasePrep record
            case_prep_obj = CasePrep(
                id=uuid.uuid4(),
                user_id=UUID(user_id),
                motion_id=motion_obj.id,
                side=side_db,
                # Will be populated by case_prep_service
                arguments=None,
                counter_arguments=None,
                evidence=None
            )
            db.add(case_prep_obj)
            db.flush()
            
            logger.info(f"CasePrep created: {case_prep_obj.id}")
            
            # STEP 3: Create DebateSession record (the match)
            skill_enum = SkillLevel[skill_level.upper()] if skill_level else SkillLevel.BEGINNER
            
            debate_session = DebateSession(
                id=uuid.uuid4(),
                user_id=UUID(user_id),
                motion_id=motion_obj.id,
                case_prep_id=case_prep_obj.id,
                format=MatchFormat.ASIAN_PARLIAMENTARY,
                human_role=role,
                skill_level=skill_enum,
                status=MatchStatus.STARTED,
                poi_enabled=True,
                started_at=datetime.now(timezone.utcezone.utc)
            )
            db.add(debate_session)
            db.commit()
            db.refresh(debate_session)
            
            logger.info(f"AP Match created: {debate_session.id} for user {user_id}")
            return debate_session
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create AP match: {str(e)}")
            raise
    
    # READ
    
    @staticmethod
    def get_match_by_id(db: Session, match_id: str) -> Optional[DebateSession]:
        """
        Get match by ID.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
        
        Returns:
            Optional[DebateSession]: Match if found, None otherwise
        """
        try:
            return db.query(DebateSession).filter(
                DebateSession.id == UUID(match_id),
                DebateSession.format == MatchFormat.ASIAN_PARLIAMENTARY
            ).first()
        except Exception as e:
            logger.error(f"Failed to get match {match_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_matches_for_user(
        db: Session,
        user_id: str,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 10
    ) -> List[DebateSession]:
        """
        Get paginated list of user's AP matches.
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
            status_filter (Optional[str]): Filter by status
            skip (int): Pagination offset
            limit (int): Results per page
        
        Returns:
            List[DebateSession]: User's AP matches
        """
        try:
            query = db.query(DebateSession).filter(
                DebateSession.user_id == UUID(user_id),
                DebateSession.format == MatchFormat.ASIAN_PARLIAMENTARY
            )
            
            if status_filter:
                # Map status_filter to MatchStatus enum
                status_enum = MatchStatus[status_filter.upper()]
                query = query.filter(DebateSession.status == status_enum)
            
            # Sort by creation date descending
            query = query.order_by(desc(DebateSession.started_at))
            
            # Paginate
            matches = query.offset(skip).limit(limit).all()
            
            logger.info(f"Retrieved {len(matches)} AP matches for user {user_id}")
            return matches
            
        except Exception as e:
            logger.error(f"Failed to list matches for user {user_id}: {str(e)}")
            raise
    
    # UPDATE
    
    @staticmethod
    def update_match_status(
        db: Session,
        match_id: str,
        new_status: str
    ) -> Optional[DebateSession]:
        """
        Update match status.
        
        Valid statuses: STARTED, FINISHED, ABORTED
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
            new_status (str): New status (e.g., "finished", "aborted")
        
        Returns:
            Optional[DebateSession]: Updated match or None
        """
        try:
            match = APMatchRepository.get_match_by_id(db, match_id)
            if not match:
                logger.warning(f"Match not found: {match_id}")
                return None
            
            # Convert string to MatchStatus enum
            status_enum = MatchStatus[new_status.upper()]
            old_status = match.status
            match.status = status_enum
            
            # Set end time if match is finishing
            if new_status.upper() in ["FINISHED", "ABORTED"]:
                match.ended_at = datetime.now(timezone.utcezone.utc)
            
            db.commit()
            db.refresh(match)
            
            logger.info(f"Match {match_id} status: {old_status.value} → {new_status}")
            return match
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update match status: {str(e)}")
            raise
    
    # DELETE
    
    @staticmethod
    def cancel_match(
        db: Session,
        match_id: str
    ) -> bool:
        """
        Cancel a match (soft delete - sets status to ABORTED).
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
        
        Returns:
            bool: True if cancelled successfully
        """
        try:
            match = APMatchRepository.get_match_by_id(db, match_id)
            if not match:
                logger.warning(f"Match not found for cancellation: {match_id}")
                return False
            
            match.status = MatchStatus.ABORTED
            match.ended_at = datetime.now(timezone.utcezone.utc)
            db.commit()
            
            logger.info(f"Match cancelled: {match_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to cancel match: {str(e)}")
            raise
    
    # QUERY HELPERS
    
    @staticmethod
    def get_ongoing_matches(db: Session, user_id: str) -> List[DebateSession]:
        """
        Get user's ongoing (STARTED) AP matches.
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
        
        Returns:
            List[DebateSession]: Ongoing matches
        """
        try:
            return db.query(DebateSession).filter(
                DebateSession.user_id == UUID(user_id),
                DebateSession.format == MatchFormat.ASIAN_PARLIAMENTARY,
                DebateSession.status == MatchStatus.STARTED
            ).order_by(desc(DebateSession.started_at)).all()
        except Exception as e:
            logger.error(f"Failed to get ongoing matches: {str(e)}")
            raise
    
    @staticmethod
    def get_match_with_motion(db: Session, match_id: str):
        """
        Get match with its associated motion.
        
        Args:
            db (Session): Database session
            match_id (str): Match UUID
        
        Returns:
            Optional[Tuple]: (DebateSession, Motion) if found
        """
        try:
            match = db.query(DebateSession).filter(
                DebateSession.id == UUID(match_id),
                DebateSession.format == MatchFormat.ASIAN_PARLIAMENTARY
            ).first()
            
            if not match:
                return None
            
            motion = db.query(Motion).filter(Motion.id == match.motion_id).first()
            return (match, motion)
            
        except Exception as e:
            logger.error(f"Failed to get match with motion: {str(e)}")
            raise
    
    # TURNS
    
    @staticmethod
    def create_turn(
        db: Session,
        session_id: str,
        turn_number: int,
        speaker_role: str,
        speaker_type: str,
        transcript_text: str,
        duration_seconds: int = 0
    ) -> Turn:
        """
        Create a new turn record for an AP debate.
        
        Called after AI agent generates a response during live debate.
        Stores the turn transcript in the database for later retrieval and analysis.
        
        Args:
            db (Session): Database session
            session_id (str): UUID of DebateSession (match)
            turn_number (int): Sequential turn number (0-indexed)
            speaker_role (str): Speaker role (e.g., "Prime Minister")
            speaker_type (str): "Human" or "AI"
            transcript_text (str): Full speech/response text
            duration_seconds (int): Duration of turn in seconds (optional)
        
        Returns:
            Turn: Created turn record
        
        Raises:
            ValueError: If session not found or invalid
            Exception: If database operation fails
        """
        try:
            # Verify session exists (optional - for validation)
            session = db.query(DebateSession).filter(
                DebateSession.id == UUID(session_id),
                DebateSession.format == MatchFormat.ASIAN_PARLIAMENTARY
            ).first()
            
            if not session:
                logger.warning(f"AP Session not found for turn creation: {session_id}")
                # Still create the turn - may be called before session verification
            
            # Create turn record
            turn = Turn(
                id=uuid.uuid4(),
                session_id=UUID(session_id),
                turn_number=turn_number,
                speaker_role=speaker_role,
                speaker_type=speaker_type,
                transcript_text=transcript_text,
                duration_seconds=duration_seconds,
                started_at=datetime.now(timezone.utcezone.utc)
            )
            
            db.add(turn)
            db.commit()
            db.refresh(turn)
            
            logger.info(f"Turn created: {turn.id} (turn #{turn_number}, speaker: {speaker_role}, type: {speaker_type})")
            return turn
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create turn for session {session_id}: {str(e)}")
            raise
