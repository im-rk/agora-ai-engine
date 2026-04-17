"""
Asian Parliamentary (AP) Services.

Service layer for AP debate format.
Contains business logic for all AP features:
- matches.py: Match management service
- debates.py: Debate state and speeches (future)
- case_prep.py: Case prep coaching (future)
- judging.py: Judging and scoring (future)
- statistics.py: User statistics and analytics (future)
"""

from .matches import APMatchService

__all__ = ["APMatchService"]
