"""Initialize the NC Foreclosures database."""

import sys
from pathlib import Path
from sqlalchemy import text
from database.connection import engine, test_connection
from database.models import Base
from common.logger import setup_logger

logger = setup_logger(__name__)


def run_schema_sql():
    """Run the schema.sql file to create tables."""
    schema_file = Path(__file__).parent / 'schema.sql'

    if not schema_file.exists():
        logger.error(f"Schema file not found: {schema_file}")
        return False

    try:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        with engine.connect() as conn:
            # Execute the schema
            conn.execute(text(schema_sql))
            conn.commit()

        logger.info("Database schema created successfully")
        return True

    except Exception as e:
        logger.error(f"Error running schema.sql: {e}")
        return False


def verify_tables():
    """Verify that all expected tables exist."""
    expected_tables = ['cases', 'case_events', 'documents', 'scrape_logs', 'user_notes']

    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
            ))
            existing_tables = [row[0] for row in result]

        missing_tables = set(expected_tables) - set(existing_tables)

        if missing_tables:
            logger.warning(f"Missing tables: {missing_tables}")
            return False

        logger.info(f"All tables verified: {', '.join(expected_tables)}")
        return True

    except Exception as e:
        logger.error(f"Error verifying tables: {e}")
        return False


def init_database():
    """Initialize the database with schema and verify."""
    logger.info("Starting database initialization...")

    # Test connection
    if not test_connection():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        return False

    # Run schema
    if not run_schema_sql():
        logger.error("Failed to create database schema")
        return False

    # Verify tables
    if not verify_tables():
        logger.error("Database verification failed")
        return False

    logger.info("✓ Database initialized successfully!")
    return True


if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
