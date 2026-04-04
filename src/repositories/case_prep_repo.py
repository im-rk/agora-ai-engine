from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from src.models.setup import CasePrep, AICallLog
from src.models.debate import DebateSession


def create_case_prep(db: Session, user_id: str, motion_id: str, side: str) -> CasePrep:
    """Creates an empty case prep container (filled by Prep Coach agent later)."""
    new_prep = CasePrep(
        user_id=user_id,
        motion_id=motion_id,
        side=side
    )

    db.add(new_prep)
    db.flush()
    return new_prep


def get_case_prep_by_id(db: Session, prep_id: str) -> Optional[CasePrep]:
    """Fetches case prep record by ID."""
    return db.query(CasePrep).filter(CasePrep.id == prep_id).first()


def get_case_prep_by_match(db: Session, match_id: str) -> Optional[CasePrep]:
    """Fetches case prep by match/session ID. Follows parent resource (Match) hierarchy."""
    session = db.query(DebateSession).filter(DebateSession.id == match_id).first()
    if not session:
        return None
    return session.case_prep


def update_case_prep(
    db: Session,
    case_prep_id: str,
    model_definition: str,
    arguments: List[Dict[str, str]],
    counter_arguments: List[str],
    evidence: List[str]
) -> CasePrep:
    """Saves AI-generated case prep data to database."""
    case_prep = db.query(CasePrep).filter(CasePrep.id == case_prep_id).first()
    
    if not case_prep:
        raise ValueError(f"CasePrep with id {case_prep_id} not found")
    
    case_prep.model_definition = model_definition
    case_prep.arguments = arguments
    case_prep.counter_arguments = counter_arguments
    case_prep.evidence = evidence
    
    db.add(case_prep)
    db.commit()
    db.refresh(case_prep)
    
    return case_prep


def save_ai_call_log(
    db: Session,
    session_id: str,
    agent_name: str,
    prompt_used: str,
    model_version: str,
    temperature: float,
    raw_output: str
) -> AICallLog:
    """Logs AI agent call to AICallLog table for observability (Langfuse)."""
    ai_log = AICallLog(
        session_id=session_id,
        agent_name=agent_name,
        prompt_used=prompt_used,
        model_version=model_version,
        temperature=temperature,
        raw_output=raw_output
    )
    
    db.add(ai_log)
    db.commit()
    db.refresh(ai_log)
    
    return ai_log
