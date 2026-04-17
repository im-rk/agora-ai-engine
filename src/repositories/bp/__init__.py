"""
British Parliamentary (BP) Repositories.

Data access layer for BP debate format.
Contains database operations for all BP features:
- matches.py: Match CRUD and queries
- case_prep.py: Case prep CRUD and queries
- debates.py: Speech recording and retrieval (future)
- judging.py: Judging data persistence (future)
"""

from .matches import BPMatchRepository
from .case_prep import BPCasePrepRepository

__all__ = ["BPMatchRepository", "BPCasePrepRepository"]
