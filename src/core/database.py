from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,           # Max persistent connections
    max_overflow=10,       # Extra connections under load
    pool_pre_ping=True,    # Auto-detect stale connections
    pool_recycle=300,      # Recycle connections every 5 minutes
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# Dependency (for FastAPI later)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()