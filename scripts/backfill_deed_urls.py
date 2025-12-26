#!/usr/bin/env python
"""
Backfill deed URLs for cases that have deed_book/deed_page from AI analysis
but haven't had deed enrichment run yet.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import CaseAnalysis, Case
from enrichments.common.models import Enrichment
from enrichments.deed import enrich_deed

def backfill_deed_urls(dry_run: bool = True):
    """
    Find cases with deed_book/deed_page but no deed_url and generate URLs.

    Args:
        dry_run: If True, only report what would be done
    """
    # First, fetch all data we need in a single session
    cases_to_process = []

    with get_session() as session:
        # Find analyses with deed info
        analyses = session.query(CaseAnalysis).filter(
            CaseAnalysis.deed_book.isnot(None),
            CaseAnalysis.deed_page.isnot(None),
            CaseAnalysis.status == 'completed'
        ).all()

        print(f"Found {len(analyses)} cases with deed_book/deed_page")

        for analysis in analyses:
            # Extract all needed data while in session
            case_id = analysis.case_id
            deed_book = analysis.deed_book
            deed_page = analysis.deed_page

            # Check if enrichment already has deed_url
            enrichment = session.query(Enrichment).filter_by(
                case_id=case_id
            ).first()

            if enrichment and enrichment.deed_url:
                continue

            case = session.get(Case, case_id)
            if not case:
                print(f"  WARN: Case {case_id} not found")
                continue

            case_number = case.case_number

            # Store all needed data
            cases_to_process.append({
                'case_id': case_id,
                'case_number': case_number,
                'deed_book': deed_book,
                'deed_page': deed_page
            })

    # Now process outside the original session
    updated = 0
    skipped = len(analyses) - len(cases_to_process)

    for case_data in cases_to_process:
        print(f"  {case_data['case_number']}: book={case_data['deed_book']}, page={case_data['deed_page']}")

        if not dry_run:
            result = enrich_deed(case_data['case_id'], case_data['deed_book'], case_data['deed_page'])
            if result.get('success'):
                print(f"    -> {result['url']}")
                updated += 1
            else:
                print(f"    -> ERROR: {result.get('error')}")
        else:
            updated += 1

    print(f"\n{'Would update' if dry_run else 'Updated'}: {updated}")
    print(f"Skipped (already have deed_url): {skipped}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Backfill deed URLs')
    parser.add_argument('--execute', action='store_true', help='Actually run updates (default is dry run)')
    args = parser.parse_args()

    backfill_deed_urls(dry_run=not args.execute)
