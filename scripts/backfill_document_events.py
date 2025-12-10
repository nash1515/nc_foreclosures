#!/usr/bin/env python3
"""
Backfill event_id for existing documents by matching filename pattern to events.

Document filename format: MM-DD-YYYY_EventType.pdf
Matches to case_events by: case_id + event_date + event_type
"""
import sys
sys.path.insert(0, '/home/ahn/projects/nc_foreclosures')

import re
from datetime import datetime
from database.connection import get_session
from database.models import Document, CaseEvent
from common.logger import setup_logger

logger = setup_logger('backfill_events')

def normalize_event_type(s):
    """
    Normalize event type for fuzzy matching.
    Removes suffix numbers, special chars, and normalizes whitespace.
    """
    if not s:
        return ''
    # Remove suffix numbers like _1, _2
    s = re.sub(r'_\d+$', '', s)
    # Remove special chars (slashes, hyphens, parens)
    s = re.sub(r'[/\-()]', '', s)
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

def parse_document_filename(filename):
    """
    Parse document filename to extract date and event type.
    Format: MM-DD-YYYY_EventType.pdf
    Returns: (date_obj, event_type) or (None, None)
    """
    # Pattern: 01-19-2023_Report of Sale Filed.pdf
    pattern = r'^(\d{2}-\d{2}-\d{4})_(.+)\.pdf$'
    match = re.match(pattern, filename, re.IGNORECASE)
    if match:
        date_str, event_type = match.groups()
        try:
            date_obj = datetime.strptime(date_str, '%m-%d-%Y').date()
            return date_obj, event_type.strip()
        except:
            pass
    return None, None

def find_event(session, case_id, event_date, event_type):
    """Find matching event by case_id, date, and type with fuzzy matching."""
    # Try exact match first
    event = session.query(CaseEvent).filter(
        CaseEvent.case_id == case_id,
        CaseEvent.event_date == event_date,
        CaseEvent.event_type == event_type
    ).first()
    if event:
        return event

    # Try normalized fuzzy match
    normalized_type = normalize_event_type(event_type)

    # Get all events for this case on this date
    events = session.query(CaseEvent).filter(
        CaseEvent.case_id == case_id,
        CaseEvent.event_date == event_date
    ).all()

    for e in events:
        normalized_event = normalize_event_type(e.event_type)

        # Try exact normalized match
        if normalized_event == normalized_type:
            return e

        # Try startswith for truncated names (at least 30 chars)
        if len(normalized_type) >= 30 and normalized_event.startswith(normalized_type[:30]):
            return e

        # Try reverse - event type might be truncated in database
        if len(normalized_event) >= 30 and normalized_type.startswith(normalized_event[:30]):
            return e

    return None

def main():
    with get_session() as session:
        # Get total document count for context
        total_docs = session.query(Document).count()
        docs_with_events = session.query(Document).filter(Document.event_id.isnot(None)).count()

        # Get all documents without event_id
        docs = session.query(Document).filter(
            Document.event_id.is_(None)
        ).all()

        print(f"Document Statistics:")
        print(f"  Total documents: {total_docs}")
        print(f"  Already matched: {docs_with_events} ({docs_with_events/total_docs*100:.1f}%)")
        print(f"  To process: {len(docs)} ({len(docs)/total_docs*100:.1f}%)")
        print()

        matched = 0
        matched_exact = 0
        matched_fuzzy = 0
        unmatched = 0
        skipped = 0

        for i, doc in enumerate(docs):
            if (i + 1) % 1000 == 0:
                print(f"Processing {i+1}/{len(docs)}...")
                session.commit()  # Commit periodically

            # Parse filename
            filename = doc.document_name or ''
            event_date, event_type = parse_document_filename(filename)

            if not event_date or not event_type:
                skipped += 1
                continue

            # Find matching event
            event = find_event(session, doc.case_id, event_date, event_type)

            if event:
                doc.event_id = event.id
                matched += 1

                # Track if it was exact or fuzzy match
                if event.event_type == event_type:
                    matched_exact += 1
                else:
                    matched_fuzzy += 1
            else:
                unmatched += 1

        session.commit()

        # Final statistics
        new_total_matched = docs_with_events + matched
        new_match_rate = new_total_matched / total_docs * 100
        old_match_rate = docs_with_events / total_docs * 100
        improvement = new_match_rate - old_match_rate

        print(f"\nResults:")
        print(f"  Matched: {matched} ({matched/len(docs)*100:.1f}% of unmatched)")
        print(f"    - Exact matches: {matched_exact}")
        print(f"    - Fuzzy matches: {matched_fuzzy}")
        print(f"  Unmatched (no event found): {unmatched}")
        print(f"  Skipped (bad filename): {skipped}")
        print()
        print(f"Overall Impact:")
        print(f"  Before: {docs_with_events}/{total_docs} matched ({old_match_rate:.1f}%)")
        print(f"  After:  {new_total_matched}/{total_docs} matched ({new_match_rate:.1f}%)")
        print(f"  Improvement: +{improvement:.1f} percentage points")

if __name__ == '__main__':
    main()
