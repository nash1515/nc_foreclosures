#!/usr/bin/env python3
"""Check document statistics across all cases.

This script provides insights into document coverage:
- Cases with/without documents
- Average documents per case by classification
- Cases with duplicate documents
- Cases with missing documents

Usage:
    python scripts/check_document_stats.py
    python scripts/check_document_stats.py --classification upcoming
    python scripts/check_document_stats.py --show-duplicates
    python scripts/check_document_stats.py --show-missing
"""

import argparse
import os
import sys
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import get_session
from database.models import Case, Document
from sqlalchemy import func
from common.logger import setup_logger

logger = setup_logger(__name__)


def get_overall_stats():
    """Get overall document statistics."""
    with get_session() as session:
        # Total cases and documents
        total_cases = session.query(Case).count()
        total_docs = session.query(Document).count()

        # Cases by classification
        by_classification = session.query(
            Case.classification,
            func.count(Case.id).label('count')
        ).group_by(Case.classification).all()

        # Cases with/without documents
        cases_with_docs = session.query(Case.id).join(Document).distinct().count()
        cases_without_docs = total_cases - cases_with_docs

        # Average documents per case
        avg_docs = total_docs / total_cases if total_cases > 0 else 0

        return {
            'total_cases': total_cases,
            'total_docs': total_docs,
            'cases_with_docs': cases_with_docs,
            'cases_without_docs': cases_without_docs,
            'avg_docs_per_case': avg_docs,
            'by_classification': {row.classification: row.count for row in by_classification}
        }


def get_classification_doc_stats(classification=None):
    """Get document stats by classification."""
    with get_session() as session:
        query = session.query(
            Case.classification,
            func.count(func.distinct(Case.id)).label('case_count'),
            func.count(Document.id).label('doc_count'),
            func.avg(func.count(Document.id)).over(partition_by=Case.classification).label('avg_docs')
        ).outerjoin(Document).group_by(Case.classification, Case.id)

        if classification:
            query = query.filter(Case.classification == classification)

        results = query.all()

        # Aggregate by classification
        stats = defaultdict(lambda: {'cases': 0, 'docs': 0, 'cases_with_docs': 0})

        for row in results:
            cls = row.classification or 'unknown'
            stats[cls]['cases'] += 1
            stats[cls]['docs'] += row.doc_count or 0
            if row.doc_count and row.doc_count > 0:
                stats[cls]['cases_with_docs'] += 1

        # Calculate averages
        for cls in stats:
            if stats[cls]['cases'] > 0:
                stats[cls]['avg_docs'] = stats[cls]['docs'] / stats[cls]['cases']
                stats[cls]['pct_with_docs'] = (stats[cls]['cases_with_docs'] / stats[cls]['cases']) * 100
            else:
                stats[cls]['avg_docs'] = 0
                stats[cls]['pct_with_docs'] = 0

        return dict(stats)


def find_duplicate_documents():
    """Find cases with duplicate document names."""
    with get_session() as session:
        # Find documents with duplicate names within the same case
        duplicates = session.query(
            Document.case_id,
            Document.document_name,
            func.count(Document.id).label('dup_count')
        ).group_by(
            Document.case_id,
            Document.document_name
        ).having(
            func.count(Document.id) > 1
        ).order_by(
            func.count(Document.id).desc()
        ).limit(20).all()

        results = []
        for dup in duplicates:
            case = session.query(Case).filter_by(id=dup.case_id).first()
            if case:
                results.append({
                    'case_number': case.case_number,
                    'case_id': dup.case_id,
                    'county': case.county_name,
                    'document_name': dup.document_name,
                    'dup_count': dup.dup_count
                })

        return results


def find_cases_without_documents(classification=None, limit=20):
    """Find cases that have no documents."""
    with get_session() as session:
        query = session.query(Case).outerjoin(Document).filter(
            Document.id.is_(None)
        )

        if classification:
            query = query.filter(Case.classification == classification)

        query = query.order_by(Case.file_date.desc()).limit(limit)

        cases = query.all()

        return [{
            'case_number': case.case_number,
            'case_id': case.id,
            'county': case.county_name,
            'classification': case.classification,
            'file_date': str(case.file_date) if case.file_date else None
        } for case in cases]


def print_stats(classification=None, show_duplicates=False, show_missing=False):
    """Print formatted statistics."""
    print("\n" + "=" * 70)
    print("DOCUMENT STATISTICS")
    print("=" * 70)

    # Overall stats
    overall = get_overall_stats()
    print(f"\nOverall:")
    print(f"  Total cases: {overall['total_cases']:,}")
    print(f"  Total documents: {overall['total_docs']:,}")
    print(f"  Cases with documents: {overall['cases_with_docs']:,} ({overall['cases_with_docs']/overall['total_cases']*100:.1f}%)")
    print(f"  Cases without documents: {overall['cases_without_docs']:,} ({overall['cases_without_docs']/overall['total_cases']*100:.1f}%)")
    print(f"  Average docs per case: {overall['avg_docs_per_case']:.1f}")

    # By classification
    print(f"\nBy Classification:")
    print(f"  {'Classification':<20} {'Cases':>8} {'Docs':>8} {'Avg':>6} {'%With':>6}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*6} {'-'*6}")

    class_stats = get_classification_doc_stats(classification)
    for cls, stats in sorted(class_stats.items()):
        print(f"  {cls or 'unknown':<20} {stats['cases']:>8,} {stats['docs']:>8,} "
              f"{stats['avg_docs']:>6.1f} {stats['pct_with_docs']:>5.1f}%")

    # Duplicates
    if show_duplicates:
        print(f"\n" + "=" * 70)
        print("CASES WITH DUPLICATE DOCUMENTS (Top 20)")
        print("=" * 70)
        duplicates = find_duplicate_documents()

        if duplicates:
            print(f"\n  {'Case Number':<18} {'County':<12} {'Document Name':<30} {'Dups':>5}")
            print(f"  {'-'*18} {'-'*12} {'-'*30} {'-'*5}")
            for dup in duplicates:
                doc_name = dup['document_name'][:28] + '..' if len(dup['document_name']) > 30 else dup['document_name']
                print(f"  {dup['case_number']:<18} {dup['county']:<12} {doc_name:<30} {dup['dup_count']:>5}")
        else:
            print("\n  No duplicate documents found!")

    # Missing documents
    if show_missing:
        print(f"\n" + "=" * 70)
        print(f"CASES WITHOUT DOCUMENTS (Top 20{' - ' + classification.upper() if classification else ''})")
        print("=" * 70)
        missing = find_cases_without_documents(classification=classification)

        if missing:
            print(f"\n  {'Case Number':<18} {'County':<12} {'Classification':<15} {'File Date':<12}")
            print(f"  {'-'*18} {'-'*12} {'-'*15} {'-'*12}")
            for case in missing:
                print(f"  {case['case_number']:<18} {case['county']:<12} "
                      f"{case['classification'] or 'unknown':<15} {case['file_date'] or 'N/A':<12}")
        else:
            print("\n  All cases have documents!")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Check document statistics across all cases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Overall stats
  python scripts/check_document_stats.py

  # Stats for specific classification
  python scripts/check_document_stats.py --classification upcoming

  # Show cases with duplicate documents
  python scripts/check_document_stats.py --show-duplicates

  # Show cases without documents
  python scripts/check_document_stats.py --show-missing

  # Full report
  python scripts/check_document_stats.py --show-duplicates --show-missing
        """
    )

    parser.add_argument('--classification', '-c',
                       choices=['upcoming', 'upset_bid', 'blocked', 'closed_sold', 'closed_dismissed'],
                       help='Filter by classification')
    parser.add_argument('--show-duplicates', '-d', action='store_true',
                       help='Show cases with duplicate document names')
    parser.add_argument('--show-missing', '-m', action='store_true',
                       help='Show cases without any documents')

    args = parser.parse_args()

    print_stats(
        classification=args.classification,
        show_duplicates=args.show_duplicates,
        show_missing=args.show_missing
    )


if __name__ == '__main__':
    main()
