from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime, timezone
from src.core.database import Base
from src.models.user import SkillLevel

class MatchFormat(str, enum.Enum):
    BRITISH_PARLIAMENTARY = "BP"
    ASIAN_PARLIAMENTARY = "AP"

class MatchStatus(str, enum.Enum):
    STARTED = "Started"
    FINISHED = "Finished"
    ABORTED = "Aborted"

class SpeakerType(str, enum.Enum):
    HUMAN = "Human"
    AI = "AI"

class POIOutcome(str, enum.Enum):
    ACCEPTED = "Accepted"
    DECLINED = "Declined"

class DebateSession(Base):
    __tablename__ = "debate_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    motion_id = Column(UUID(as_uuid=True), ForeignKey("motions.id"), nullable=False)
    case_prep_id = Column(UUID(as_uuid=True), ForeignKey("case_preps.id"), nullable=True) 
    
    format = Column(Enum(MatchFormat), nullable=False)
    human_role = Column(String, nullable=False)
    skill_level = Column(Enum(SkillLevel), nullable=False) 
    status = Column(Enum(MatchStatus), default=MatchStatus.STARTED)
    poi_enabled = Column(Boolean, default=True)
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="debate_sessions")
    motion = relationship("Motion", back_populates="debate_sessions")
    case_prep = relationship("CasePrep", back_populates="debate_sessions")
    turns = relationship("Turn", back_populates="session")
    pois = relationship("POI", back_populates="session")
    results = relationship("AdjudicationResult", back_populates="session", uselist=False)
    performances = relationship("UserPerformance", back_populates="session")

class Turn(Base):
    __tablename__ = "turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("debate_sessions.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    speaker_role = Column(String, nullable=False)
    speaker_type = Column(Enum(SpeakerType), nullable=False)
    
    transcript_text = Column(Text, nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    stt_confidence_avg = Column(Float, nullable=True)
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("DebateSession", back_populates="turns")
    pois = relationship("POI", back_populates="turn")

class POI(Base):
    __tablename__ = "pois"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("debate_sessions.id"), nullable=False)
    turn_id = Column(UUID(as_uuid=True), ForeignKey("turns.id"), nullable=False)
    
    offered_by = Column(Enum(SpeakerType), nullable=False)
    poi_text = Column(Text, nullable=False)
    outcome = Column(Enum(POIOutcome), nullable=False)
    response_text = Column(Text, nullable=True)
    offered_at_second = Column(Integer, nullable=False)

    # Relationships
    session = relationship("DebateSession", back_populates="pois")
    turn = relationship("Turn", back_populates="pois")