"""
Schemas package.

Contains:
- common.py: Common schemas (APIResponse, status codes, enums)
- response/: Response DTOs for all endpoints
- request/: Request DTOs for all endpoints (to be created)
"""

from .common import (
    APIResponse,
    APIStatusCode,
    DebateFormatEnum,
    SkillLevelEnum,
    SpeakerTypeEnum,
    DebateStatusEnum
)

__all__ = [
    "APIResponse",
    "APIStatusCode",
    "DebateFormatEnum",
    "SkillLevelEnum",
    "SpeakerTypeEnum",
    "DebateStatusEnum"
]
