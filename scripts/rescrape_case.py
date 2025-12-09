#!/usr/bin/env python3
"""Rescrape a single case to fix document issues.

This script:
1. Deletes all existing documents for the case from the database
2. Re-downloads all documents using case_monitor.py
3. Useful for fixing duplicate documents or missing PDFs

Usage:
    python scripts/rescrape_case.py 25SP001706-910
    python scripts/rescrape_case.py 25SP001706-910 --keep-files  # Don't delete files, just DB records
    python scripts/rescrape_case.py 25SP001706-910 --dry-run    # Show what would be done
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import get_session
from database.models import Case, Document
from scraper.case_monitor import CaseMonitor
from common.logger import setup_logger
from common.county_codes import get_county_name

logger = setup_logger(__name__)


def delete_case_documents(case_id: int, keep_files: bool = False):
    """
    Delete all documents for a case from the database.

    Args:
        case_id: Database ID of the case
        keep_files: If True, keep the PDF files on disk (just delete DB records)

    Returns:
        Tuple of (count deleted from DB, count deleted from disk)
    """
    db_deleted = 0
    files_deleted = 0

    with get_session() as session:
        # Get all documents
        docs = session.query(Document).filter_by(case_id=case_id).all()

        logger.info(f"Found {len(docs)} documents to delete")

        # Track unique file paths
        file_paths = set()
        for doc in docs:
            if doc.file_path:
                file_paths.add(doc.file_path)

        # Delete from database
        for doc in docs:
            session.delete(doc)
            db_deleted += 1

        session.commit()
        logger.info(f"Deleted {db_deleted} document records from database")

        # Delete files from disk if requested
        if not keep_files:
            for file_path in file_paths:
                try:
                    p = Path(file_path)
                    if p.exists():
                        p.unlink()
                        files_deleted += 1
                        logger.debug(f"  Deleted file: {file_path}")
                except Exception as e:
                    logger.warning(f"  Failed to delete {file_path}: {e}")

            logger.info(f"Deleted {files_deleted} files from disk")
        else:
            logger.info(f"Keeping {len(file_paths)} files on disk (--keep-files)")

    return db_deleted, files_deleted


def rescrape_case(case_number: str, keep_files: bool = False, dry_run: bool = False):
    """
    Rescrape a single case to fix document issues.

    Args:
        case_number: Case number (e.g., '25SP001706-910')
        keep_files: If True, keep PDF files on disk (just delete DB records)
        dry_run: If True, show what would be done without actually doing it

    Returns:
        True if successful, False otherwise
    """
    logger.info("=" * 60)
    logger.info(f"RESCRAPING CASE: {case_number}")
    logger.info("=" * 60)

    # Get the case from database
    with get_session() as session:
        case = session.query(Case).filter_by(case_number=case_number).first()

        if not case:
            logger.error(f"Case {case_number} not found in database")
            return False

        # Detach from session so we can use it later
        session.expunge(case)

    logger.info(f"Case ID: {case.id}")
    logger.info(f"County: {case.county_name}")
    logger.info(f"Classification: {case.classification}")
    logger.info(f"Case URL: {case.case_url}")

    if dry_run:
        logger.info("\n[DRY RUN] Would perform the following:")
        logger.info("1. Delete all documents for this case from database")
        if not keep_files:
            logger.info("2. Delete all PDF files from disk")
        logger.info("3. Re-download all documents from NC Courts portal")

        # Count documents
        with get_session() as session:
            doc_count = session.query(Document).filter_by(case_id=case.id).count()
        logger.info(f"\nWould delete {doc_count} document records")

        return True

    # Step 1: Delete existing documents
    logger.info("\nStep 1: Deleting existing documents...")
    db_deleted, files_deleted = delete_case_documents(case.id, keep_files=keep_files)

    # Step 2: Re-download documents using case_monitor
    logger.info("\nStep 2: Re-downloading documents from portal...")

    # Create a monitor instance
    monitor = CaseMonitor(
        max_workers=1,
        headless=False,  # Use visible browser for reliability
        max_retries=3,
        retry_delay=2.0
    )

    # Process just this one case
    results = monitor.run(cases=[case], dry_run=False)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("RESCRAPE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Database records deleted: {db_deleted}")
    if not keep_files:
        logger.info(f"Files deleted from disk: {files_deleted}")
    logger.info(f"Events added: {results.get('events_added', 0)}")
    logger.info(f"Bid updates: {results.get('bid_updates', 0)}")

    # Check how many documents we have now
    with get_session() as session:
        new_doc_count = session.query(Document).filter_by(case_id=case.id).count()
    logger.info(f"Documents after rescrape: {new_doc_count}")

    if results.get('errors'):
        logger.error("\nErrors encountered:")
        for error in results['errors']:
            logger.error(f"  - {error}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Rescrape a single case to fix document issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Rescrape case (deletes docs and files, re-downloads everything)
  python scripts/rescrape_case.py 25SP001706-910

  # Keep PDF files on disk, just refresh DB records
  python scripts/rescrape_case.py 25SP001706-910 --keep-files

  # Preview what would be done
  python scripts/rescrape_case.py 25SP001706-910 --dry-run
        """
    )

    parser.add_argument('case_number', help='Case number to rescrape (e.g., 25SP001706-910)')
    parser.add_argument('--keep-files', action='store_true',
                       help='Keep PDF files on disk (just delete DB records)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually doing it')

    args = parser.parse_args()

    # Environment check
    if 'PYTHONPATH' not in os.environ:
        logger.warning("PYTHONPATH not set - this may cause import issues")
        logger.warning("Run: export PYTHONPATH=$(pwd)")

    # Run the rescrape
    success = rescrape_case(
        case_number=args.case_number,
        keep_files=args.keep_files,
        dry_run=args.dry_run
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
