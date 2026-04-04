"""
Prep Coach DTOs: Data Transfer Objects for case preparation.

These Pydantic models enforce strict validation on AI output
before saving to database.
"""

from typing import List
from pydantic import BaseModel, Field


class Argument(BaseModel):
    """Single debate argument with claim, reasoning, and impact."""
    claim: str = Field(description="The central claim being argued")
    reasoning: str = Field(description="Logical support for the claim")
    impact: str = Field(description="Real-world consequence if claim is true")


class AIPrepResult(BaseModel):
    """Complete case preparation output from Prep Coach agent."""
    model_definition: str = Field(description="Interpretation of the debate motion")
    arguments: List[Argument] = Field(max_length=5, description="Main arguments for the side")
    counter_arguments: List[str] = Field(description="Anticipated opposing arguments")
    evidence: List[str] = Field(description="Supporting facts and reasoning")
