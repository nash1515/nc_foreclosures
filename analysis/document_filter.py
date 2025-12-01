"""Document filter - Skip list management.

Learns from AI evaluations to skip low-value documents in future analyses.
Reduces token usage and API costs over time.
"""

from typing import Optional

from sqlalchemy import text

from database.connection import get_session
from common.logger import setup_logger

logger = setup_logger(__name__)

# Default patterns to always skip (procedural documents)
DEFAULT_SKIP_PATTERNS = [
    "Certificate of Service",
    "Affidavit of Service",
    "Affidavit of Mailing",
    "Proof of Service",
    "Return of Service",
    "Summons",
]


class DocumentFilter:
    """Manages document skip patterns."""

    def __init__(self):
        """Initialize filter with default patterns."""
        self._cached_patterns = None

    def should_skip(self, document_name: str) -> bool:
        """
        Check if a document should be skipped.

        Args:
            document_name: Name of the document

        Returns:
            True if document matches a skip pattern
        """
        if not document_name:
            return False

        patterns = self.get_patterns()
        doc_lower = document_name.lower()

        for pattern in patterns:
            if pattern.lower() in doc_lower:
                return True

        return False

    def get_patterns(self) -> list:
        """Get all active skip patterns."""
        if self._cached_patterns is not None:
            return self._cached_patterns

        patterns = list(DEFAULT_SKIP_PATTERNS)

        try:
            with get_session() as session:
                result = session.execute(
                    text("SELECT pattern FROM document_skip_patterns")
                )
                for row in result:
                    if row[0] not in patterns:
                        patterns.append(row[0])
        except Exception as e:
            logger.debug(f"Could not load skip patterns from DB: {e}")

        self._cached_patterns = patterns
        return patterns

    def add_pattern(
        self,
        pattern: str,
        pattern_type: str = "learned",
        added_by: str = "ai_analysis",
    ) -> bool:
        """
        Add a new skip pattern.

        Args:
            pattern: Pattern to match against document names
            pattern_type: Type of pattern ("default", "learned", "manual")
            added_by: Who added the pattern

        Returns:
            True if pattern was added, False if already exists
        """
        with get_session() as session:
            # Check if pattern exists
            result = session.execute(
                text("SELECT id FROM document_skip_patterns WHERE pattern = :pattern"),
                {"pattern": pattern}
            )
            if result.fetchone():
                return False

            session.execute(
                text("""
                    INSERT INTO document_skip_patterns (pattern, pattern_type, added_by)
                    VALUES (:pattern, :pattern_type, :added_by)
                """),
                {
                    "pattern": pattern,
                    "pattern_type": pattern_type,
                    "added_by": added_by,
                }
            )
            session.commit()

        # Clear cache
        self._cached_patterns = None
        logger.info(f"Added skip pattern: {pattern}")
        return True

    def increment_skip_count(self, pattern: str) -> None:
        """Increment the skip count for a pattern."""
        with get_session() as session:
            session.execute(
                text("""
                    UPDATE document_skip_patterns
                    SET skip_count = skip_count + 1
                    WHERE pattern = :pattern
                """),
                {"pattern": pattern}
            )
            session.commit()

    def update_from_evaluations(
        self,
        evaluations: list,
        threshold: int = 3,
    ) -> list:
        """
        Learn new skip patterns from AI document evaluations.

        Args:
            evaluations: List of document evaluation dicts from AI
            threshold: Minimum number of "not useful" ratings to add pattern

        Returns:
            List of newly added patterns
        """
        # Count "not useful" ratings by document type
        useless_counts = {}

        for eval_item in evaluations:
            if not eval_item.get("useful", True):
                doc_type = eval_item.get("doc_type", "Unknown")
                useless_counts[doc_type] = useless_counts.get(doc_type, 0) + 1

        # Add patterns that exceed threshold
        added = []
        for doc_type, count in useless_counts.items():
            if count >= threshold:
                if self.add_pattern(doc_type, pattern_type="learned"):
                    added.append(doc_type)

        if added:
            logger.info(f"Learned {len(added)} new skip patterns: {added}")

        return added

    def get_stats(self) -> dict:
        """Get skip pattern statistics."""
        with get_session() as session:
            result = session.execute(
                text("""
                    SELECT pattern_type, COUNT(*), SUM(skip_count)
                    FROM document_skip_patterns
                    GROUP BY pattern_type
                """)
            )

            stats = {"by_type": {}, "total_patterns": 0, "total_skips": 0}
            for row in result:
                stats["by_type"][row[0]] = {
                    "count": row[1],
                    "skips": row[2] or 0,
                }
                stats["total_patterns"] += row[1]
                stats["total_skips"] += row[2] or 0

            return stats


def get_skip_patterns() -> list:
    """Get current skip patterns."""
    return DocumentFilter().get_patterns()


def should_skip_document(document_name: str) -> bool:
    """Check if document should be skipped."""
    return DocumentFilter().should_skip(document_name)


def learn_from_evaluations(evaluations: list) -> list:
    """Learn new patterns from AI evaluations."""
    return DocumentFilter().update_from_evaluations(evaluations)
