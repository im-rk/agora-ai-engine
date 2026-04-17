"""
Asian Parliamentary (AP) Services.

Service layer for AP debate format.
Contains business logic for all AP features:
- matches.py: Match management service
- case_prep.py: Case prep generation service
- debates.py: Debate state and speeches (future)
- judging.py: Judging and scoring (future)
- statistics.py: User statistics and analytics (future)
"""

from .matches import APMatchService
from .case_prep import APCasePrepService

__all__ = ["APMatchService", "APCasePrepService"]
