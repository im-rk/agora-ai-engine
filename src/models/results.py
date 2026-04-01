from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from src.core.database import Base

class AdjudicationResult(Base):
    __tablename__ = "adjudication_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("debate_sessions.id"), nullable=False, unique=True)
    
    winning_team = Column(String, nullable=False) # e.g., 'Government' or 'Opposition'
    gov_total_score = Column(Float, nullable=False)
    opp_total_score = Column(Float, nullable=False)
    
    clash_table = Column(JSONB, nullable=False)
    speaker_scores = Column(JSONB, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("DebateSession", back_populates="results")

class UserPerformance(Base):
    __tablename__ = "user_performance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("debate_sessions.id"), nullable=False)
    
    speaker_role = Column(String, nullable=False)
    total_score = Column(Float, nullable=False)
    
    argument_score = Column(Float, nullable=False)
    rebuttal_score = Column(Float, nullable=False)
    structure_score = Column(Float, nullable=False)
    delivery_score = Column(Float, nullable=False)
    poi_score = Column(Float, nullable=False)
    
    written_feedback = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="performances")
    session = relationship("DebateSession", back_populates="performances")