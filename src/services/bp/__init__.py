"""
British Parliamentary (BP) Services.

Service layer for BP debate format.
Contains business logic for all BP features:
- matches.py: Match management service
- case_prep.py: Case prep generation service
- debates.py: Debate state and speeches (future)
- judging.py: Judging and scoring (future)
- statistics.py: User statistics and analytics (future)
"""

from .matches import BPMatchService
from .case_prep import BPCasePrepService

__all__ = ["BPMatchService", "BPCasePrepService"]
