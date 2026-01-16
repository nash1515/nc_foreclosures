#!/usr/bin/env python3
"""
One-time backfill script to enrich all existing upset_bid cases with PropWire URLs.

Usage:
    PYTHONPATH=$(pwd) python -m enrichments.prop_wire.backfill
"""

import logging
from sqlalchemy import select
from database.connection import get_session
from database.models import Case
from enrichments.common.models import Enrichment
from enrichments.prop_wire.enricher import PropWireEnricher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_cases_needing_propwire_enrichment():
    """
    Query all cases where classification = 'upset_bid' AND propwire_url is NULL.

    Returns:
        List of case IDs that need PropWire enrichment
    """
    with get_session() as session:
        # Join cases with enrichments to find cases missing propwire_url
        stmt = (
            select(Case.id)
            .outerjoin(Enrichment, Case.id == Enrichment.case_id)
            .where(Case.classification == 'upset_bid')
            .where(
                (Enrichment.propwire_url.is_(None)) | (Enrichment.case_id.is_(None))
            )
        )

        result = session.execute(stmt)
        case_ids = [row[0] for row in result]

    return case_ids


def backfill_propwire_enrichments():
    """
    Main backfill function.

    Processes all upset_bid cases missing PropWire URLs.
    """
    logger.info("Starting PropWire backfill for upset_bid cases...")

    # Get cases that need enrichment
    case_ids = get_cases_needing_propwire_enrichment()
    total_cases = len(case_ids)

    if total_cases == 0:
        logger.info("No cases need PropWire enrichment. All done!")
        return

    logger.info(f"Found {total_cases} cases needing PropWire enrichment")

    # Initialize enricher
    enricher = PropWireEnricher()

    # Track results
    success_count = 0
    error_count = 0
    review_count = 0

    # Process each case
    for idx, case_id in enumerate(case_ids, 1):
        logger.info(f"[{idx}/{total_cases}] Processing case_id={case_id}")

        try:
            result = enricher.enrich(case_id)

            if result.success:
                success_count += 1
                logger.info(f"  ✓ Success: {result.url}")
            elif result.review_needed:
                review_count += 1
                logger.warning(f"  ⚠ Review needed: {result.error}")
            else:
                error_count += 1
                logger.error(f"  ✗ Error: {result.error}")

        except Exception as e:
            error_count += 1
            logger.error(f"  ✗ Exception while enriching case_id={case_id}: {e}", exc_info=True)
            # Continue with next case
            continue

    # Summary
    logger.info("\n" + "="*60)
    logger.info("PropWire Backfill Complete")
    logger.info("="*60)
    logger.info(f"Total cases processed: {total_cases}")
    logger.info(f"Successful enrichments: {success_count}")
    logger.info(f"Needs manual review: {review_count}")
    logger.info(f"Errors: {error_count}")
    logger.info("="*60)


if __name__ == '__main__':
    backfill_propwire_enrichments()
