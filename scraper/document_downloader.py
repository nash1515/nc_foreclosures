"""Document download utilities for case healing."""

from typing import List
from database.connection import get_session
from database.models import Case, CaseEvent, Document
from common.logger import setup_logger
import os
import requests

logger = setup_logger(__name__)

DOCUMENTS_DIR = "documents"


def download_case_documents(case_id: int, force: bool = False) -> int:
    """
    Download documents for a case from event URLs.

    Args:
        case_id: Database ID of the case
        force: If True, re-download even if file exists

    Returns:
        Number of documents downloaded
    """
    downloaded = 0

    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            logger.error(f"Case {case_id} not found")
            return 0

        events = session.query(CaseEvent).filter(
            CaseEvent.case_id == case_id,
            CaseEvent.document_url.isnot(None)
        ).all()

        case_dir = os.path.join(DOCUMENTS_DIR, case.county_code, case.case_number)
        os.makedirs(case_dir, exist_ok=True)

        for event in events:
            if not event.document_url:
                continue

            # Generate filename from event
            filename = f"{event.event_date}_{event.event_type[:30]}.pdf".replace("/", "_").replace(" ", "_")
            filepath = os.path.join(case_dir, filename)

            if os.path.exists(filepath) and not force:
                continue

            try:
                response = requests.get(event.document_url, timeout=30)
                response.raise_for_status()

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                # Update or create document record
                doc = session.query(Document).filter_by(
                    case_id=case_id,
                    document_name=filename
                ).first()

                if not doc:
                    doc = Document(
                        case_id=case_id,
                        document_name=filename,
                        file_path=filepath,
                        event_id=event.id
                    )
                    session.add(doc)
                else:
                    doc.file_path = filepath
                    doc.ocr_text = None  # Clear for re-OCR

                downloaded += 1
                logger.info(f"Downloaded: {filepath}")

            except Exception as e:
                logger.error(f"Failed to download {event.document_url}: {e}")

        session.commit()

    return downloaded
