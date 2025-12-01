"""Case analyzer - Main orchestrator for AI analysis.

Coordinates prompt building, API calls, and result storage.
Handles batch analysis of upset_bid cases with smart re-analysis triggers.
"""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from database.connection import get_session
from analysis.api_client import APIClient, estimate_cost
from analysis.prompt_builder import build_prompt, estimate_tokens
from analysis.knowledge_base import get_status_blockers, get_key_events
from common.logger import setup_logger

logger = setup_logger(__name__)


class CaseAnalyzer:
    """Orchestrates AI analysis of foreclosure cases."""

    def __init__(self, model: str = "opus", dry_run: bool = False):
        """
        Initialize case analyzer.

        Args:
            model: Claude model to use ("opus", "sonnet", "haiku")
            dry_run: If True, preview prompts without API calls
        """
        self.model = model
        self.dry_run = dry_run
        self.api_client = None if dry_run else APIClient(model=model)

    def analyze_case(
        self,
        case_id: int,
        skip_patterns: list = None,
        force: bool = False,
    ) -> Optional[dict]:
        """
        Analyze a single case.

        Args:
            case_id: Database ID of the case
            skip_patterns: Document patterns to skip
            force: If True, re-analyze even if recent analysis exists

        Returns:
            Analysis result dict, or None if skipped
        """
        # Check if analysis already exists (unless forced)
        if not force:
            existing = self._get_latest_analysis(case_id)
            if existing:
                logger.info(f"Case {case_id} already analyzed at {existing['analyzed_at']}")
                return None

        # Build prompt
        try:
            system_prompt, user_prompt, doc_count = build_prompt(case_id, skip_patterns)
        except ValueError as e:
            logger.error(f"Failed to build prompt for case {case_id}: {e}")
            return None

        # Estimate tokens
        token_estimate = estimate_tokens(system_prompt, user_prompt)
        logger.info(f"Case {case_id}: {doc_count} documents, ~{token_estimate} tokens")

        if self.dry_run:
            logger.info(f"[DRY RUN] Would call API with ~{token_estimate} tokens")
            return {
                "dry_run": True,
                "case_id": case_id,
                "document_count": doc_count,
                "token_estimate": token_estimate,
                "cost_estimate": estimate_cost(len(user_prompt), self.model),
            }

        # Call API
        try:
            result, input_tokens, output_tokens, cost = self.api_client.call(
                system_prompt, user_prompt
            )
        except Exception as e:
            logger.error(f"API call failed for case {case_id}: {e}")
            return None

        # Store result
        analysis_id = self._store_analysis(
            case_id, result, input_tokens, output_tokens, cost
        )

        # Update case classification if needed
        if result.get("recommended_classification"):
            self._update_classification(case_id, result)

        logger.info(
            f"Case {case_id} analyzed: ${cost:.4f}, "
            f"valid_upset_bid={result.get('is_valid_upset_bid')}, "
            f"confidence={result.get('confidence_score')}"
        )

        return result

    def analyze_pending(
        self,
        limit: int = None,
        skip_patterns: list = None,
    ) -> dict:
        """
        Analyze all pending upset_bid cases.

        Args:
            limit: Maximum cases to analyze
            skip_patterns: Document patterns to skip

        Returns:
            Summary dict with counts and costs
        """
        # Get cases needing analysis
        cases = self._get_cases_needing_analysis(limit)
        logger.info(f"Found {len(cases)} cases needing analysis")

        results = {
            "total": len(cases),
            "analyzed": 0,
            "skipped": 0,
            "failed": 0,
            "total_cost": 0.0,
        }

        for case in cases:
            case_id = case["id"]
            case_number = case["case_number"]

            logger.info(f"Analyzing {case_number} (ID: {case_id})...")

            result = self.analyze_case(case_id, skip_patterns)

            if result is None:
                results["skipped"] += 1
            elif result.get("dry_run"):
                results["analyzed"] += 1
                results["total_cost"] += result.get("cost_estimate", 0)
            elif "error" in result:
                results["failed"] += 1
            else:
                results["analyzed"] += 1
                # Cost is stored in the analysis record

        return results

    def check_reanalysis_needed(self, case_id: int) -> bool:
        """
        Check if case needs re-analysis based on new events.

        Args:
            case_id: Database ID of the case

        Returns:
            True if re-analysis should be triggered
        """
        with get_session() as session:
            # Get latest analysis timestamp
            result = session.execute(
                text("""
                    SELECT analyzed_at FROM ai_analysis
                    WHERE case_id = :case_id
                    ORDER BY analyzed_at DESC
                    LIMIT 1
                """),
                {"case_id": case_id}
            )
            row = result.fetchone()
            if not row:
                return True  # Never analyzed

            last_analyzed = row[0]

            # Check for significant events since last analysis
            key_events = get_key_events()
            trigger_types = (
                key_events.get("extends_upset_period", []) +
                key_events.get("potential_blockers", []) +
                key_events.get("case_closed", [])
            )

            result = session.execute(
                text("""
                    SELECT COUNT(*) FROM case_events
                    WHERE case_id = :case_id
                      AND created_at > :last_analyzed
                      AND event_type = ANY(:trigger_types)
                """),
                {
                    "case_id": case_id,
                    "last_analyzed": last_analyzed,
                    "trigger_types": trigger_types,
                }
            )
            count = result.scalar()

            if count > 0:
                logger.info(f"Case {case_id} has {count} new significant events")
                return True

            return False

    def _get_cases_needing_analysis(self, limit: int = None) -> list:
        """Get upset_bid cases that haven't been analyzed."""
        with get_session() as session:
            query = """
                SELECT c.id, c.case_number, c.county_name
                FROM cases c
                WHERE c.classification = 'upset_bid'
                  AND NOT EXISTS (
                    SELECT 1 FROM ai_analysis a WHERE a.case_id = c.id
                  )
                ORDER BY c.file_date DESC
            """
            if limit:
                query += f" LIMIT {limit}"

            result = session.execute(text(query))
            return [
                {"id": row[0], "case_number": row[1], "county": row[2]}
                for row in result
            ]

    def _get_latest_analysis(self, case_id: int) -> Optional[dict]:
        """Get the most recent analysis for a case."""
        with get_session() as session:
            result = session.execute(
                text("""
                    SELECT id, analyzed_at, is_valid_upset_bid, confidence_score
                    FROM ai_analysis
                    WHERE case_id = :case_id
                    ORDER BY analyzed_at DESC
                    LIMIT 1
                """),
                {"case_id": case_id}
            )
            row = result.fetchone()
            if row:
                return {
                    "id": row[0],
                    "analyzed_at": row[1],
                    "is_valid_upset_bid": row[2],
                    "confidence_score": row[3],
                }
            return None

    def _store_analysis(
        self,
        case_id: int,
        result: dict,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> int:
        """Store analysis result in database."""
        with get_session() as session:
            insert_result = session.execute(
                text("""
                    INSERT INTO ai_analysis (
                        case_id, analyzed_at, model_version,
                        is_valid_upset_bid, status_blockers, recommended_classification,
                        upset_deadline, deadline_extended, extension_count,
                        current_bid_amount, estimated_total_liens, mortgage_info, tax_info,
                        research_flags, document_evaluations,
                        analysis_notes, confidence_score, discrepancies,
                        tokens_used, cost_estimate
                    ) VALUES (
                        :case_id, NOW(), :model_version,
                        :is_valid_upset_bid, :status_blockers, :recommended_classification,
                        :upset_deadline, :deadline_extended, :extension_count,
                        :current_bid_amount, :estimated_total_liens, :mortgage_info, :tax_info,
                        :research_flags, :document_evaluations,
                        :analysis_notes, :confidence_score, :discrepancies,
                        :tokens_used, :cost_estimate
                    )
                    RETURNING id
                """),
                {
                    "case_id": case_id,
                    "model_version": self.model,
                    "is_valid_upset_bid": result.get("is_valid_upset_bid"),
                    "status_blockers": json.dumps(result.get("status_blockers", [])),
                    "recommended_classification": result.get("recommended_classification"),
                    "upset_deadline": result.get("upset_deadline"),
                    "deadline_extended": result.get("deadline_extended"),
                    "extension_count": result.get("extension_count", 0),
                    "current_bid_amount": result.get("current_bid_amount"),
                    "estimated_total_liens": result.get("estimated_total_liens"),
                    "mortgage_info": json.dumps(result.get("mortgage_info", [])),
                    "tax_info": json.dumps(result.get("tax_info", {})),
                    "research_flags": json.dumps(result.get("research_flags", [])),
                    "document_evaluations": json.dumps(result.get("document_evaluations", [])),
                    "analysis_notes": result.get("analysis_notes"),
                    "confidence_score": result.get("confidence_score"),
                    "discrepancies": json.dumps(result.get("discrepancies", [])),
                    "tokens_used": input_tokens + output_tokens,
                    "cost_estimate": cost,
                }
            )
            session.commit()
            return insert_result.scalar()

    def _update_classification(self, case_id: int, result: dict) -> None:
        """Update case classification based on analysis.

        IMPORTANT: AI analysis should only REFINE existing classifications,
        not downgrade clear rule-based classifications. The rule-based
        classifier (extraction/classifier.py) handles initial classification.

        AI can:
        - Change 'upset_bid' to 'pending' (if deadline passed)
        - Change 'upset_bid' to 'needs_review' (if blockers found)
        - Keep 'upset_bid' (confirmed valid)

        AI should NOT:
        - Change 'upcoming' to anything (no Report of Sale = definitely upcoming)
        - Change 'closed' to anything
        """
        recommended = result.get("recommended_classification")
        confidence = result.get("confidence_score", 0)

        if not recommended:
            return

        with get_session() as session:
            # Get current classification
            current = session.execute(
                text("SELECT classification FROM cases WHERE id = :case_id"),
                {"case_id": case_id}
            ).scalar()

            # Don't let AI override rule-based 'upcoming' classification
            # 'upcoming' means no Report of Sale - that's a factual determination
            if current == 'upcoming' and recommended != 'upcoming':
                logger.warning(
                    f"Case {case_id}: AI suggested '{recommended}' but case is 'upcoming' "
                    f"(no Report of Sale). Keeping 'upcoming'."
                )
                return

            # Don't let AI override 'closed' classification
            if current == 'closed':
                logger.warning(
                    f"Case {case_id}: AI suggested '{recommended}' but case is already 'closed'. "
                    f"Keeping 'closed'."
                )
                return

            # Only update if classification changed
            if current != recommended:
                logger.info(
                    f"Case {case_id}: classification {current} -> {recommended}"
                )

                session.execute(
                    text("""
                        UPDATE cases
                        SET classification = :classification, updated_at = NOW()
                        WHERE id = :case_id
                    """),
                    {"case_id": case_id, "classification": recommended}
                )
                session.commit()


def analyze_case(
    case_id: int,
    model: str = "opus",
    dry_run: bool = False,
    skip_patterns: list = None,
) -> Optional[dict]:
    """
    Convenience function to analyze a single case.

    Args:
        case_id: Database ID of the case
        model: Claude model to use
        dry_run: If True, preview without API calls
        skip_patterns: Document patterns to skip

    Returns:
        Analysis result dict
    """
    analyzer = CaseAnalyzer(model=model, dry_run=dry_run)
    return analyzer.analyze_case(case_id, skip_patterns)


def analyze_pending(
    model: str = "opus",
    limit: int = None,
    dry_run: bool = False,
    skip_patterns: list = None,
) -> dict:
    """
    Convenience function to analyze all pending upset_bid cases.

    Args:
        model: Claude model to use
        limit: Maximum cases to analyze
        dry_run: If True, preview without API calls
        skip_patterns: Document patterns to skip

    Returns:
        Summary dict with counts and costs
    """
    analyzer = CaseAnalyzer(model=model, dry_run=dry_run)
    return analyzer.analyze_pending(limit=limit, skip_patterns=skip_patterns)
