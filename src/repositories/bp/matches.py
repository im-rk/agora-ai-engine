"""
British Parliamentary (BP) Match Repository.

Database layer for BP match persistence using DebateSession model.

Responsibilities:
- Create new BP matches (DebateSession + Motion + CasePrep)
- Retrieve matches by ID
- List matches with filtering
- Update match status
- Cancel/delete matches

Maps BP schemas to actual database models:
- Motion: Debate topic (shared with AP)
- CasePrep: User's prepared case for a team
- DebateSession: THE match record (format=BP)

Key difference from AP:
- format = MatchFormat.BRITISH_PARLIAMENTARY
- 4 teams instead of 2 sides
- 8 speakers instead of 6
"""

import logging
import uuid
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models.debate import DebateSession, MatchFormat, MatchStatus, Turn
from src.models.setup import Motion, MotionCategory, CasePrep, AICallLog
from src.models.user import SkillLevel

logger = logging.getLogger(__name__)


# ============================================================================
# TEAM → SIDE MAPPING
# BP has 4 teams, but CasePrep.side stores "Government" or "Opposition"
# This maps team names to sides for the CasePrep record.
# ============================================================================
TEAM_TO_SIDE = {
    "opening_government": "Government",
    "opening_opposition": "Opposition",
    "closing_government": "Government",
    "closing_opposition": "Opposition",
}


class BPMatchRepository:
    """
    Repository for British Parliamentary match database operations.
    
    Uses DebateSession as the primary match model (same table as AP).
    Filters by format=BRITISH_PARLIAMENTARY to isolate BP matches.
    """
    
    # CREATE
    
    @staticmethod
    def create_match(
        db: Session,
        user_id: str,
        motion: str,
        team: str,
        role: str,
        skill_level: str = "BEGINNER"
    ) -> DebateSession:
        """
        Create a new BP match.
        
        Flow:
        1. Create Motion record (debate topic)
        2. Create CasePrep record (user's prepared case)
        3. Create DebateSession record (the match)
        
        Args:
            db (Session): Database session
            user_id (str): UUID of user creating match
            motion (str): Debate motion text (e.g., "This house believes...")
            team (str): BP team ("opening_government", "closing_opposition", etc.)
            role (str): BP role (e.g., "prime_minister", "member_of_government")
            skill_level (str): User's skill level (BEGINNER, INTERMEDIATE, ADVANCED)
        
        Returns:
            DebateSession: Created debate session (the match)
        
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails
        """
        try:
            # Convert team to side for CasePrep record
            side_db = TEAM_TO_SIDE.get(team.lower(), "Government")
            
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
                format=MatchFormat.BRITISH_PARLIAMENTARY,  # ← BP format
                human_role=role,
                skill_level=skill_enum,
                status=MatchStatus.STARTED,
                poi_enabled=True,
                started_at=datetime.now(timezone.utc)
            )
            db.add(debate_session)
            db.commit()
            db.refresh(debate_session)
            
            logger.info(f"BP Match created: {debate_session.id} for user {user_id}")
            return debate_session
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create BP match: {str(e)}")
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
                DebateSession.format == MatchFormat.BRITISH_PARLIAMENTARY  # ← BP filter
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
        Get paginated list of user's BP matches.
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
            status_filter (Optional[str]): Filter by status
            skip (int): Pagination offset
            limit (int): Results per page
        
        Returns:
            List[DebateSession]: User's BP matches
        """
        try:
            query = db.query(DebateSession).filter(
                DebateSession.user_id == UUID(user_id),
                DebateSession.format == MatchFormat.BRITISH_PARLIAMENTARY  # ← BP filter
            )
            
            if status_filter:
                # Map status_filter to MatchStatus enum
                status_enum = MatchStatus[status_filter.upper()]
                query = query.filter(DebateSession.status == status_enum)
            
            # Sort by creation date descending
            query = query.order_by(desc(DebateSession.started_at))
            
            # Paginate
            matches = query.offset(skip).limit(limit).all()
            
            logger.info(f"Retrieved {len(matches)} BP matches for user {user_id}")
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
            match = BPMatchRepository.get_match_by_id(db, match_id)
            if not match:
                logger.warning(f"Match not found: {match_id}")
                return None
            
            # Convert string to MatchStatus enum
            status_enum = MatchStatus[new_status.upper()]
            old_status = match.status
            match.status = status_enum
            
            # Set end time if match is finishing
            if new_status.upper() in ["FINISHED", "ABORTED"]:
                match.ended_at = datetime.now(timezone.utc)
            
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
            match = BPMatchRepository.get_match_by_id(db, match_id)
            if not match:
                logger.warning(f"Match not found for cancellation: {match_id}")
                return False
            
            match.status = MatchStatus.ABORTED
            match.ended_at = datetime.now(timezone.utc)
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
        Get user's ongoing (STARTED) BP matches.
        
        Args:
            db (Session): Database session
            user_id (str): User UUID
        
        Returns:
            List[DebateSession]: Ongoing matches
        """
        try:
            return db.query(DebateSession).filter(
                DebateSession.user_id == UUID(user_id),
                DebateSession.format == MatchFormat.BRITISH_PARLIAMENTARY,  # ← BP filter
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
                DebateSession.format == MatchFormat.BRITISH_PARLIAMENTARY  # ← BP filter
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
        Create a new turn record for a BP debate.
        
        Called after AI agent generates a response during live debate.
        Stores the turn transcript in the database for later retrieval and analysis.
        
        Args:
            db (Session): Database session
            session_id (str): UUID of DebateSession (match)
            turn_number (int): Sequential turn number (0-indexed)
            speaker_role (str): Speaker role (e.g., "Member of Government")
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
                DebateSession.format == MatchFormat.BRITISH_PARLIAMENTARY  # ← BP filter
            ).first()
            
            if not session:
                logger.warning(f"BP Session not found for turn creation: {session_id}")
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
                started_at=datetime.now(timezone.utc)
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
    
    @staticmethod
    def update_turn_timing(
        db: Session,
        match_id: str,
        turn_index: int,
        duration_seconds: float,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
        stt_confidence: Optional[float] = None
    ) -> Optional[Turn]:
        """
        Update turn timing with duration and end timestamp.
        
        Called when AI speech completes (frontend-measured timing).
        Persists actual speech duration for analytics.
        
        Args:
            db (Session): Database session
            match_id (str): UUID of DebateSession (match)
            turn_index (int): Turn number (0-indexed)
            duration_seconds (float): Duration of speech in seconds (frontend-measured)
            started_at (Optional[str]): ISO timestamp when speech started (from frontend)
            ended_at (Optional[str]): ISO timestamp when speech ended (from frontend)
            stt_confidence (Optional[float]): Average STT confidence (0.0 to 1.0)
        
        Returns:
            Optional[Turn]: Updated turn record, or None if not found
        
        Raises:
            Exception: If database operation fails
        """
        try:
            # Find turn by session_id and turn_number
            turn = db.query(Turn).filter(
                Turn.session_id == UUID(match_id),
                Turn.turn_number == turn_index
            ).first()
            
            if not turn:
                logger.warning(
                    f"Turn not found for update: match={match_id}, turn_index={turn_index}"
                )
                return None
            
            # Only update if not already set (idempotent)
            if not turn.ended_at:
                turn.duration_seconds = int(duration_seconds)
                if stt_confidence is not None:
                    turn.stt_confidence_avg = stt_confidence
                
                # Use frontend-provided timestamps if available
                if started_at:
                    turn.started_at = datetime.fromisoformat(started_at)
                if ended_at:
                    turn.ended_at = datetime.fromisoformat(ended_at)
                
                db.commit()
                db.refresh(turn)
                
                logger.info(
                    f"Turn timing updated: {turn.id} "
                    f"(duration: {turn.duration_seconds}s, "
                    f"confidence: {turn.stt_confidence_avg}, "
                    f"started_at: {turn.started_at}, ended_at: {turn.ended_at})"
                )
                return turn
            else:
                logger.debug(
                    f"Turn {turn.id} already has ended_at set. Skipping idempotent update."
                )
                return turn
            
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to update turn timing for match {match_id}, turn {turn_index}: {str(e)}"
            )
            raise


def log_ai_call(
    db: Session,
    session_id: str,
    agent_name: str,
    prompt_used: str,
    model_version: str,
    temperature: float,
    raw_output: Optional[str] = None
) -> AICallLog:
    """
    Log an AI/LLM call to the database for observability.
    
    Args:
        db (Session): Database session
        session_id (str): UUID of DebateSession
        agent_name (str): Name of agent making the call
        prompt_used (str): Prompt sent to LLM (truncated to 4000 chars)
        model_version (str): Model name/version used
        temperature (float): Temperature parameter used
        raw_output (str): Raw output from LLM (optional, truncated to 4000 chars)
    
    Returns:
        AICallLog: Created log record
    
    Raises:
        Exception: If database operation fails
    """
    try:
        log_entry = AICallLog(
            id=uuid.uuid4(),
            session_id=UUID(session_id),
            agent_name=agent_name,
            prompt_used=prompt_used[:4000],  # Truncate to reasonable size
            model_version=model_version,
            temperature=temperature,
            raw_output=raw_output[:4000] if raw_output else None
        )
        
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        
        logger.info(f"AI call logged: {agent_name} for session {session_id}")
        return log_entry
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to log AI call for session {session_id}: {str(e)}")
        raise
