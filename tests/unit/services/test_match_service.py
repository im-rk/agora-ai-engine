import uuid
import pytest
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.models.user import User
from src.services.match_service import start_new_match


@pytest.mark.asyncio
async def test_start_new_match(monkeypatch):
    db: Session = SessionLocal()

    # ----------------------------
    # 🔥 MOCK prepare_case
    # ----------------------------
    async def mock_prepare_case(*args, **kwargs):
        return {
            "model_definition": "mock",
            "arguments": [],
            "counter_arguments": [],
            "evidence": []
        }

    monkeypatch.setattr(
        "src.services.match_service.prepare_case",
        mock_prepare_case
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
    # 2️⃣ Prepare request
    # ----------------------------
    class DummyRequest:
        motion_text = "Ban AI in education"
        side = "Opposition"
        format = "Asian Parliamentary"
        user_id = str(user.id)

    request = DummyRequest()

    # ----------------------------
    # 3️⃣ Call service
    # ----------------------------
    result = await start_new_match(db=db, request=request)

    # ----------------------------
    # 4️⃣ Assertions
    # ----------------------------
    assert result is not None
    assert "session_id" in result
    assert "case_prep_id" in result

    print("✅ Match Service Test Passed")