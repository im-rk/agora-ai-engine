"""
Unit tests for Pydantic schemas (validation rules).
These tests are fast - no database, no network calls.
"""
import pytest
from pydantic import ValidationError
from src.schemas.user_schema import UserCreate


def test_user_create_valid():
    """Test that valid user data passes validation."""
    user = UserCreate(
        email="test@example.com",
        password="SecurePass123!",
        display_name="Test User",
        skill_level="Beginner"
    )
    assert user.email == "test@example.com"
    assert user.display_name == "Test User"


def test_user_create_invalid_email():
    """Test that invalid email fails validation."""
    with pytest.raises(ValidationError):
        UserCreate(
            email="not-an-email",
            password="SecurePass123!",
            display_name="Test User",
            skill_level="Beginner"
        )


def test_user_create_weak_password():
    """Test that weak password fails validation (if rule exists)."""
    # TODO: Implement password strength validation in schema
    pass
