"""
Database engine and session factory.

DATABASE_URL is read from the environment (via config.py).
- SQLite  → used automatically during local dev and unit tests (no Docker required)
- Postgres → used in Docker / production

connect_args={"check_same_thread": False} is SQLite-only; it's required because
FastAPI runs in an async context where multiple threads can share a connection.
For Postgres this arg is not needed and is not passed.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings

# SQLite needs check_same_thread=False; Postgres doesn't need any special args
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    # For SQLite, enable WAL mode for better concurrent read performance
    # (irrelevant for Postgres but harmless to leave the listener registered)
)

# Enable WAL mode for SQLite — better read concurrency, still serialized writes
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency that yields a database session and ensures it is closed
    after the request, even if an exception is raised.

    Usage:
        @router.get("/")
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
