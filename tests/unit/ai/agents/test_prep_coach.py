# """
# Unit tests for the Prep Coach AI agent.
# Tests the AI prompt generation (with mocked LLM responses).
# """
# import pytest
# from unittest.mock import Mock, patch
# # from src.ai.agents.prep_coach import PrepCoachAgent  # TODO: Import your agent


# def test_prep_coach_generates_case():
#     """Test that prep coach generates a case structure."""
#     # TODO: Mock the LLM client and test case generation
#     # with patch("src.ai.clients.openai_client.OpenAIClient.generate") as mock_llm:
#     #     mock_llm.return_value = {
#     #         "model_definition": "This is a model case...",
#     #         "arguments": ["Arg 1", "Arg 2"],
#     #         "counter_arguments": ["Counter 1"],
#     #         "evidence": ["Evidence 1"]
#     #     }
#     #     
#     #     agent = PrepCoachAgent()
#     #     result = agent.generate_case(
#     #         motion="This House would ban social media",
#     #         side="Government"
#     #     )
#     #     
#     #     assert "arguments" in result
#     #     assert len(result["arguments"]) > 0
#     #     mock_llm.assert_called_once()
#     pass


# def test_prep_coach_handles_invalid_side():
#     """Test that invalid side (not Gov/Opp) raises error."""
#     # TODO: Test error handling
#     pass


# def test_prep_coach_prompt_format():
#     """Test that the generated prompt has the correct format."""
#     # TODO: Test prompt generation without calling LLM
#     # agent = PrepCoachAgent()
#     # prompt = agent.build_prompt(
#     #     motion="Test motion",
#     #     side="Government"
#     # )
#     # assert "Government" in prompt
#     # assert "Test motion" in prompt
#     pass


# def test_prep_coach_difficulty_levels():
#     """Test that different skill levels generate different prompts."""
#     # TODO: Test that Beginner, Intermediate, Advanced levels work
#     pass

import uuid
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.models.setup import CasePrep, Motion, MotionCategory
from src.models.user import User
from src.ai.agents.prep_coach import generate_case_prep


def test_generate_case_prep():
    db: Session = SessionLocal()

    # ----------------------------
    # 1️⃣ Create User (required FK)
    # ----------------------------
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4()}@example.com",  # unique email
        password_hash="dummy",
        display_name="Test User"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # ----------------------------
    # 2️⃣ Create Motion (required FK)
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
    # 3️⃣ Create CasePrep (valid FKs)
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
    # 4️⃣ Run Prep Coach
    # ----------------------------
    success = generate_case_prep(
        db=db,
        case_prep_id=str(case_prep.id),
        motion_text="Ban AI in education",
        side="Opposition"
    )

    # ----------------------------
    # 5️⃣ Assertions
    # ----------------------------
    assert success is True

    updated = db.query(CasePrep).filter(CasePrep.id == case_prep.id).first()

    assert updated is not None
    assert updated.arguments is not None
    assert len(updated.arguments) > 0

    assert updated.counter_arguments is not None
    assert len(updated.counter_arguments) > 0

    assert updated.evidence is not None
    assert len(updated.evidence) > 0

    print("Prep Coach Test Passed")