"""
Asian Parliamentary (AP) Repositories.

Data access layer for AP debate format.
Contains database operations for all AP features:
- matches.py: Match CRUD and queries
- case_prep.py: Case prep CRUD and queries
- debates.py: Speech recording and retrieval (future)
- judging.py: Judging data persistence (future)
"""

from .matches import APMatchRepository
from .case_prep import APCasePrepRepository

__all__ = ["APMatchRepository", "APCasePrepRepository"]
