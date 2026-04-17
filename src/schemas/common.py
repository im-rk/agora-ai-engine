"""
Common schemas used across all endpoints.

Includes:
- APIResponse wrapper
- Status codes
- Enums
"""

from enum import Enum
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

T = TypeVar('T')


class APIStatusCode(str, Enum):
    """Standard API response status codes."""
    SUCCESS = "success"
    ERROR = "error"
    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.
    
    Used for all API responses to ensure consistency.
    
    Example:
        {
            "status": "success",
            "message": "User created successfully",
            "data": { ... },
            "error_code": null,
            "timestamp": "2025-01-15T10:30:00Z"
        }
    """
    status: APIStatusCode
    message: str
    data: Optional[T] = None
    error_code: Optional[str] = None
    timestamp: str = ""
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utcezone.utc).isoformat()


class DebateFormatEnum(str, Enum):
    """Supported debate formats."""
    ASIAN_PARLIAMENTARY = "AP"
    BRITISH_PARLIAMENTARY = "BP"


class SkillLevelEnum(str, Enum):
    """User skill levels."""
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


class SpeakerTypeEnum(str, Enum):
    """Speaker type in debate."""
    HUMAN = "Human"
    AI = "AI"


class DebateStatusEnum(str, Enum):
    """Debate status."""
    WAITING = "waiting"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    ABORTED = "aborted"
