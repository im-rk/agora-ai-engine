from sqlalchemy.orm import Session
from src.models.debate import DebateSession
from src.models.setup import CasePrep

def create_debate_session(db:Session,user_id:str,format_type:str,side:str) -> DebateSession:
    """Creates a new debate session in the database"""
    new_session=DebateSession(
        user_id=user_id,
        format=format_type,
        human_role=side
    )

    db.add(new_session)
    db.flush()
    return new_session

def create_case_prep(db:Session,user_id:str,side:str)->CasePrep:
    """Creates a new empty case prep container in the database"""
    new_prep=CasePrep(
        user_id=user_id,
        side=side
    )

    db.add(new_prep)
    db.flush()
    return new_prep

def get_case_prep_by_id(db: Session, prep_id: str):
    """Fetches a specific case prep container from the database."""
    return db.query(CasePrep).filter(CasePrep.id == prep_id).first()