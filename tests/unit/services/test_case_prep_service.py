import uuid
import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from src.core.database import SessionLocal
from src.models.user import User
from src.models.setup import Motion, MotionCategory, CasePrep, ArgumentEmbedding
from src.models.debate import DebateSession, MatchFormat, MatchStatus
from src.services.case_prep_service import prepare_case


@pytest.mark.asyncio
async def test_prepare_case(monkeypatch):
    db: Session = SessionLocal()

    # ----------------------------
    # 🔥 MOCK AI RESPONSE
    # ----------------------------
    async def mock_generate_case_prep(*args, **kwargs):
        return {
            "model_definition": "AI should not dominate education",
            "arguments": [
                {
                    "claim": "AI reduces critical thinking",
                    "reasoning": "Students rely too much on AI",
                    "impact": "Leads to weaker intellectual development"
                }
            ],
            "counter_arguments": ["AI improves efficiency"],
            "evidence": ["Studies show over-reliance reduces retention"]
        }

    # 🔥 PATCH AI AGENT
    monkeypatch.setattr(
        "src.services.case_prep_service.generate_case_prep",
        mock_generate_case_prep
    )

    # ----------------------------
    # 1️⃣ Create User
    # ----------------------------
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4()}@example.com",
        password_hash="dummy",
        display_name="Test User"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # ----------------------------
    # 2️⃣ Create Motion
    # ----------------------------
    motion = Motion(
        id=uuid.uuid4(),
        motion_text="Ban AI in education",
        category=MotionCategory.CUSTOM,
        is_custom=True
    )
    db.add(motion)
    db.commit()
    db.refresh(motion)

    # ----------------------------
    # 3️⃣ Create Debate Session ✅ (FIX)
    # ----------------------------
    session = DebateSession(
        id=uuid.uuid4(),
        user_id=user.id,
        motion_id=motion.id,
        format=MatchFormat.ASIAN_PARLIAMENTARY,
        human_role="Opposition",
        skill_level=user.skill_level,
        status=MatchStatus.STARTED,
        started_at=datetime.now(timezone.utc)
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    # ----------------------------
    # 4️⃣ Create CasePrep
    # ----------------------------
    case_prep = CasePrep(
        id=uuid.uuid4(),
        user_id=user.id,
        motion_id=motion.id,
        side="Opposition"
    )
    db.add(case_prep)
    db.commit()
    db.refresh(case_prep)

    # ----------------------------
    # 5️⃣ Call Service (FIXED session_id)
    # ----------------------------
    result = await prepare_case(
        db=db,
        user_id=str(user.id),
        motion_id=str(motion.id),
        session_id=str(session.id),  # ✅ FIX HERE
        case_prep_id=str(case_prep.id),
        motion_text="Ban AI in education",
        side="Opposition",
        format="AP"
    )

    # ----------------------------
    # 6️⃣ Assertions
    # ----------------------------
    assert result is not None
    assert "arguments" in result

    updated = db.query(CasePrep).filter(CasePrep.id == case_prep.id).first()

    assert updated.arguments is not None
    assert updated.counter_arguments is not None
    assert updated.evidence is not None

    # ----------------------------
    # 7️⃣ Embeddings check
    # ----------------------------
    embeddings = db.query(ArgumentEmbedding).filter(
        ArgumentEmbedding.case_prep_id == case_prep.id
    ).all()

    assert len(embeddings) > 0

    print("✅ Case Prep Service Test Passed")