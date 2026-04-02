from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Boolean, Float, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid
import enum
from datetime import datetime, timezone
from src.core.database import Base

from sqlalchemy import UniqueConstraint

__table_args__ = (
    UniqueConstraint("user_id", "motion_id", "side", name="unique_case_prep"),
)


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
    embeddings = relationship("ArgumentEmbedding", back_populates="case_prep")
    

class ArgumentEmbedding(Base):
    __tablename__ = "argument_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_prep_id = Column(UUID(as_uuid=True), ForeignKey("case_preps.id"), nullable=False)
    
    content = Column(String, nullable=False)
    embedding = Column(Vector(1024), nullable=False)
    argument_type = Column(String) 
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    case_prep = relationship("CasePrep", back_populates="embeddings")

class AICallLog(Base):
    __tablename__ = "ai_call_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("debate_sessions.id"), nullable=False)
    
    agent_name = Column(String, nullable=False)
    prompt_used = Column(Text, nullable=False)  
    model_version = Column(String, nullable=False)
    temperature = Column(Float, nullable=False)
    
    raw_output = Column(Text, nullable=True)  # Should be Text, not DateTime
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    session = relationship("DebateSession", back_populates="ai_logs")


