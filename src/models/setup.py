from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime, timezone
from src.core.database import Base

class MotionCategory(str, enum.Enum):
    POLITICS = "Politics"
    TECHNOLOGY = "Technology"
    ECONOMICS = "Economics"
    PHILOSOPHY = "Philosophy"
    CUSTOM = "Custom"

class Motion(Base):
    __tablename__ = "motions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    motion_text = Column(String, nullable=False)
    category = Column(Enum(MotionCategory), nullable=False)
    is_custom = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    case_preps = relationship("CasePrep", back_populates="motion")
    debate_sessions = relationship("DebateSession", back_populates="motion")

class CasePrep(Base):
    __tablename__ = "case_preps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    motion_id = Column(UUID(as_uuid=True), ForeignKey("motions.id"), nullable=False)
    side = Column(String, nullable=False) # e.g., 'Government' or 'Opposition'
    
    # Storing the complex AI structures as JSON
    model_definition = Column(JSONB, nullable=True)
    arguments = Column(JSONB, nullable=True)
    counter_arguments = Column(JSONB, nullable=True)
    evidence = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="case_preps")
    motion = relationship("Motion", back_populates="case_preps")
    debate_sessions = relationship("DebateSession", back_populates="case_prep")