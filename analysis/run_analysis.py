#!/usr/bin/env python3
"""CLI entry point for AI analysis.

Usage:
    # Analyze specific case by ID
    PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --case-id 123

    # Analyze specific case by case number
    PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --case 24SP001234-910

    # Analyze all pending upset_bid cases
    PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --pending

    # Dry run (preview without API calls)
    PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --pending --dry-run

    # Limit batch size
    PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --pending --limit 10

    # Use different model
    PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --pending --model sonnet

    # Force re-analysis
    PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --case-id 123 --force
"""

import argparse
import sys

from sqlalchemy import text

from database.connection import get_session
from analysis.case_analyzer import CaseAnalyzer
from analysis.document_filter import get_skip_patterns
from common.logger import setup_logger

logger = setup_logger(__name__)


def get_case_id_from_number(case_number: str) -> int:
    """Look up case ID from case number."""
    with get_session() as session:
        result = session.execute(
            text("SELECT id FROM cases WHERE case_number = :case_number"),
            {"case_number": case_number}
        )
        row = result.fetchone()
        if row:
            return row[0]
        return None


def get_case_classification(case_id: int) -> str:
    """Look up case classification."""
    with get_session() as session:
        result = session.execute(
            text("SELECT classification FROM cases WHERE id = :case_id"),
            {"case_id": case_id}
        )
        row = result.fetchone()
        if row:
            return row[0]
        return None


def print_analysis_result(result: dict) -> None:
    """Pretty print analysis result."""
    if not result:
        print("No result returned")
        return

    if result.get("dry_run"):
        print("\n=== DRY RUN ===")
        print(f"  Case ID: {result['case_id']}")
        print(f"  Documents: {result['document_count']}")
        print(f"  Est. Tokens: {result['token_estimate']}")
        print(f"  Est. Cost: ${result['cost_estimate']:.4f}")
        return

    print("\n=== ANALYSIS RESULT ===")
    print(f"  Valid Upset Bid: {result.get('is_valid_upset_bid')}")
    print(f"  Classification: {result.get('recommended_classification')}")
    print(f"  Confidence: {result.get('confidence_score')}")
    print(f"  Upset Deadline: {result.get('upset_deadline')}")
    bid = result.get('current_bid_amount') or 0
    print(f"  Current Bid: ${bid:,.2f}")

    # Mortgage info
    mortgages = result.get("mortgage_info", [])
    if mortgages:
        print("\n  MORTGAGE INFO:")
        for m in mortgages:
            holder = m.get('holder', 'Unknown')
            amount = m.get('amount', 0)
            rate = m.get('rate', 'N/A')
            date = m.get('date', 'N/A')
            print(f"    - {holder}: ${amount:,.2f} ({rate}) dated {date}")

    # Tax info
    tax_info = result.get("tax_info", {})
    if tax_info and any(tax_info.values()):
        print("\n  TAX INFO:")
        if tax_info.get('outstanding'):
            print(f"    Outstanding: ${tax_info['outstanding']:,.2f}")
        if tax_info.get('county_assessed_value'):
            print(f"    Assessed Value: ${tax_info['county_assessed_value']:,.2f}")
        if tax_info.get('year'):
            print(f"    Tax Year: {tax_info['year']}")

    # Estimated liens
    liens = result.get('estimated_total_liens')
    if liens:
        print(f"\n  Est. Total Liens: ${liens:,.2f}")

    blockers = result.get("status_blockers", [])
    if blockers:
        print("\n  STATUS BLOCKERS:")
        for b in blockers:
            print(f"    - [{b.get('type')}] {b.get('description')}")

    flags = result.get("research_flags", [])
    if flags:
        print("\n  RESEARCH FLAGS:")
        for f in flags:
            severity = f.get("severity", "medium").upper()
            print(f"    - [{severity}] {f.get('type')}: {f.get('description')}")

    discrepancies = result.get("discrepancies", [])
    if discrepancies:
        print("\n  DISCREPANCIES:")
        for d in discrepancies:
            print(f"    - {d.get('field')}: expected {d.get('expected')}, found {d.get('found')}")

    notes = result.get("analysis_notes")
    if notes:
        print(f"\n  NOTES:\n    {notes[:500]}...")


def main():
    parser = argparse.ArgumentParser(
        description="AI Analysis for NC Foreclosure Cases"
    )

    # Case selection
    case_group = parser.add_mutually_exclusive_group(required=True)
    case_group.add_argument(
        "--case-id",
        type=int,
        help="Database ID of case to analyze"
    )
    case_group.add_argument(
        "--case",
        type=str,
        help="Case number to analyze (e.g., 24SP001234-910)"
    )
    case_group.add_argument(
        "--pending",
        action="store_true",
        help="Analyze all pending upset_bid cases"
    )

    # Options
    parser.add_argument(
        "--model",
        choices=["opus", "sonnet", "haiku"],
        default="opus",
        help="Claude model to use (default: opus)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making API calls"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum cases to analyze (for --pending)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-analyze even if recent analysis exists"
    )
    parser.add_argument(
        "--show-skip-patterns",
        action="store_true",
        help="Show current document skip patterns"
    )

    args = parser.parse_args()

    # Show skip patterns if requested
    if args.show_skip_patterns:
        patterns = get_skip_patterns()
        print(f"\nDocument Skip Patterns ({len(patterns)} total):")
        for p in patterns:
            print(f"  - {p}")
        return 0

    # Initialize analyzer
    analyzer = CaseAnalyzer(model=args.model, dry_run=args.dry_run)
    skip_patterns = get_skip_patterns()

    if args.dry_run:
        logger.info("Running in DRY RUN mode - no API calls will be made")

    # Analyze single case
    if args.case_id or args.case:
        case_id = args.case_id
        if args.case:
            case_id = get_case_id_from_number(args.case)
            if not case_id:
                print(f"Case not found: {args.case}")
                return 1

        # Verify case is upset_bid before analyzing
        classification = get_case_classification(case_id)
        if classification != 'upset_bid':
            print(f"Case {case_id} is '{classification}', not 'upset_bid'.")
            print("AI analysis only runs on upset_bid cases.")
            print("\nReason: Cases must have a Report of Sale filed before AI analysis")
            print("can verify the upset bid period, extract financials, and calculate deadlines.")
            return 1

        logger.info(f"Analyzing case ID {case_id}...")
        result = analyzer.analyze_case(
            case_id,
            skip_patterns=skip_patterns,
            force=args.force,
        )
        print_analysis_result(result)
        return 0

    # Analyze pending cases
    if args.pending:
        logger.info("Analyzing pending upset_bid cases...")
        results = analyzer.analyze_pending(
            limit=args.limit,
            skip_patterns=skip_patterns,
        )

        print("\n=== BATCH ANALYSIS COMPLETE ===")
        print(f"  Total cases: {results['total']}")
        print(f"  Analyzed: {results['analyzed']}")
        print(f"  Skipped (already analyzed): {results['skipped']}")
        print(f"  Failed: {results['failed']}")
        if args.dry_run:
            print(f"  Estimated total cost: ${results['total_cost']:.2f}")

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
