"""
Unit tests for debate schemas (Pydantic validation).
Tests your MatchStartRequest, TurnCreate, etc.
"""
import pytest
from pydantic import ValidationError
# from src.schemas.debate_schema import MatchStartRequest, TurnCreate  # TODO: Import your schemas


def test_match_start_request_valid():
    """Test that valid match start data passes validation."""
    # TODO: Uncomment when MatchStartRequest is implemented
    # match_request = MatchStartRequest(
    #     motion_id="550e8400-e29b-41d4-a716-446655440000",
    #     format="AP",
    #     skill_level="Intermediate",
    #     human_role="PM",
    #     poi_enabled=True
    # )
    # assert match_request.format == "AP"
    # assert match_request.skill_level == "Intermediate"
    pass


def test_match_start_request_invalid_format():
    """Test that invalid format fails validation."""
    # TODO: Test that format must be either "AP" or "BP"
    # with pytest.raises(ValidationError):
    #     MatchStartRequest(
    #         motion_id="550e8400-e29b-41d4-a716-446655440000",
    #         format="INVALID",  # Should fail
    #         skill_level="Intermediate",
    #         human_role="PM"
    #     )
    pass


def test_turn_create_valid():
    """Test that valid turn data passes validation."""
    # TODO: Test TurnCreate schema
    pass


def test_turn_create_missing_required_fields():
    """Test that missing required fields fail validation."""
    # TODO: Test required fields
    pass
