"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from common.config import config
from common.logger import setup_logger

logger = setup_logger(__name__)

# Create engine with connection pooling
engine = create_engine(
    config.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Thread-safe session
Session = scoped_session(SessionLocal)


@contextmanager
def get_session():
    """
    Provide a transactional scope for database operations.

    Usage:
        with get_session() as session:
            case = session.query(Case).first()
            ...
    """
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def get_db_session():
    """
    Get a database session (for use in web frameworks).

    Usage:
        session = get_db_session()
        try:
            # ... do work
            session.commit()
        finally:
            session.close()
    """
    return Session()


def close_session():
    """Close the current session."""
    Session.remove()


def test_connection():
    """Test database connection."""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
