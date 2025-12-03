"""PDF downloading functionality for NC Courts Portal.

The portal uses Angular with document buttons that trigger downloads.
This module handles:
1. Extracting document URLs from case detail pages
2. Downloading PDFs using Playwright
3. Storing files and creating database records
"""

import os
import re
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import Page, Download

from common.config import config
from common.logger import setup_logger
from database.connection import get_session
from database.models import Document

logger = setup_logger(__name__)


def extract_document_info_from_page(page: Page):
    """
    Extract document information from a case detail page using JavaScript.

    The portal uses Angular with document buttons that have ng-click handlers.
    Document buttons typically have aria-label containing "document" or
    are in event rows with document icons.

    Args:
        page: Playwright page object on a case detail page

    Returns:
        list: List of dicts with document info:
            - index: Document index/number
            - event_type: Type of event this document is attached to
            - event_date: Date of the event
            - has_download: Whether download button exists
    """
    documents = []

    try:
        # Find all event containers that have document indicators
        # The portal shows a document icon (IMG with title) for events with attached documents
        doc_info = page.evaluate(r'''
            () => {
                const docs = [];

                // Method 1: Look for IMG elements with title containing "document"
                // These are clickable icons that trigger PDF downloads
                const docIcons = document.querySelectorAll('img[title*="document" i], img.roa-clickable[title*="document" i]');
                docIcons.forEach((img, idx) => {
                    // Try to find the parent event row to get context
                    const eventRow = img.closest('[ng-repeat*="event"]') || img.closest('tr') || img.closest('div');
                    let eventType = '';
                    let eventDate = '';

                    if (eventRow) {
                        // Extract text content for event info
                        const text = eventRow.textContent || '';
                        // Try to find date pattern
                        const dateMatch = text.match(/(\d{2}\/\d{2}\/\d{4})/);
                        if (dateMatch) {
                            eventDate = dateMatch[1];
                        }
                    }

                    docs.push({
                        index: idx + 1,
                        buttonIndex: idx,
                        eventType: eventType,
                        eventDate: eventDate,
                        title: img.getAttribute('title') || '',
                        hasDownload: true
                    });
                });

                // Method 2: Fallback - look for buttons with aria-label containing "document"
                if (docs.length === 0) {
                    const docButtons = document.querySelectorAll('button[aria-label*="document" i]');
                    docButtons.forEach((btn, idx) => {
                        const eventRow = btn.closest('[ng-repeat*="event"]') || btn.closest('tr') || btn.closest('div');
                        let eventDate = '';
                        if (eventRow) {
                            const text = eventRow.textContent || '';
                            const dateMatch = text.match(/(\d{2}\/\d{2}\/\d{4})/);
                            if (dateMatch) {
                                eventDate = dateMatch[1];
                            }
                        }
                        docs.push({
                            index: idx + 1,
                            buttonIndex: idx,
                            eventType: '',
                            eventDate: eventDate,
                            title: btn.getAttribute('aria-label') || '',
                            hasDownload: true
                        });
                    });
                }

                return {
                    buttonDocs: docs,
                    docCount: docs.length
                };
            }
        ''')

        logger.debug(f"Found {len(doc_info.get('buttonDocs', []))} document buttons, {doc_info.get('indexCount', 0)} index references")

        return doc_info.get('buttonDocs', [])

    except Exception as e:
        logger.error(f"Error extracting document info: {e}")
        return []


def click_document_button_and_download(page: Page, button_index: int, download_path: Path, timeout: int = 30000):
    """
    Click a document icon/button and handle the download.

    Args:
        page: Playwright page object
        button_index: Index of the document icon to click
        download_path: Path where to save the downloaded file
        timeout: Download timeout in milliseconds

    Returns:
        str: Path to downloaded file, or None if download failed
    """
    try:
        # Set up download handler
        with page.expect_download(timeout=timeout) as download_info:
            # Click the document icon by index
            # First try IMG elements (primary method), then fallback to buttons
            page.evaluate(f'''
                () => {{
                    // Try IMG elements first (portal uses IMG with title for doc icons)
                    let docElements = document.querySelectorAll('img[title*="document" i]');
                    if (docElements.length === 0) {{
                        // Fallback to buttons
                        docElements = document.querySelectorAll('button[aria-label*="document" i]');
                    }}
                    if (docElements[{button_index}]) {{
                        docElements[{button_index}].click();
                    }}
                }}
            ''')

        download = download_info.value

        # Generate filename from suggested name or use default
        suggested_name = download.suggested_filename
        if not suggested_name or suggested_name == 'download':
            suggested_name = f"document_{button_index + 1}.pdf"

        # Ensure it ends with .pdf
        if not suggested_name.lower().endswith('.pdf'):
            suggested_name += '.pdf'

        # Save the file
        file_path = download_path / suggested_name
        download.save_as(str(file_path))

        logger.info(f"  Downloaded: {suggested_name}")
        return str(file_path)

    except Exception as e:
        logger.warning(f"  Download failed for button {button_index}: {e}")
        return None


def download_case_documents(page: Page, case_id: int, county: str, case_number: str):
    """
    Download all documents for a case from its detail page.

    This function should be called while on the case detail page.
    It will:
    1. Find all document buttons on the page
    2. Click each and download the PDF
    3. Save to filesystem organized by county/case_number
    4. Create Document records in database

    Args:
        page: Playwright page object (on case detail page)
        case_id: Database ID of the case
        county: County name (e.g., 'wake')
        case_number: Case number (e.g., '24SP000437-910')

    Returns:
        int: Number of documents downloaded
    """
    logger.info(f"Checking for documents to download...")

    # Get storage path for this case
    download_path = config.get_pdf_path(county, case_number)
    logger.debug(f"  Download path: {download_path}")

    # Extract document info from page
    doc_buttons = extract_document_info_from_page(page)

    if not doc_buttons:
        logger.info(f"  No documents found")
        return 0

    logger.info(f"  Found {len(doc_buttons)} document(s) to download")

    downloaded_count = 0

    for doc_info in doc_buttons:
        button_index = doc_info.get('buttonIndex', 0)
        event_date = doc_info.get('eventDate', '')

        # Try to download
        file_path = click_document_button_and_download(
            page,
            button_index,
            download_path
        )

        if file_path:
            # Parse event date if available
            doc_date = None
            if event_date:
                try:
                    doc_date = datetime.strptime(event_date, '%m/%d/%Y').date()
                except ValueError:
                    pass

            # Create database record
            try:
                with get_session() as session:
                    document = Document(
                        case_id=case_id,
                        document_name=Path(file_path).name,
                        file_path=file_path,
                        document_date=doc_date
                    )
                    session.add(document)
                    session.commit()

                downloaded_count += 1
                logger.debug(f"    Saved document record to database")

            except Exception as e:
                logger.error(f"    Failed to save document record: {e}")

        # Small delay between downloads to be polite
        time.sleep(0.5)

    logger.info(f"  Downloaded {downloaded_count}/{len(doc_buttons)} documents")
    return downloaded_count


def download_documents_for_event(page: Page, case_id: int, county: str, case_number: str,
                                  event_index: int, event_type: str = None, event_date: str = None):
    """
    Download document for a specific event by its index.

    Alternative approach: download documents one at a time as events are processed.

    Args:
        page: Playwright page object
        case_id: Database ID of the case
        county: County name
        case_number: Case number
        event_index: Zero-based index of the event in the events list
        event_type: Optional event type for naming
        event_date: Optional event date string (MM/DD/YYYY)

    Returns:
        str: Path to downloaded file, or None
    """
    download_path = config.get_pdf_path(county, case_number)

    try:
        # Check if this event has a document button
        has_doc = page.evaluate(f'''
            () => {{
                const eventDivs = document.querySelectorAll('[ng-repeat*="event"]');
                if (eventDivs[{event_index}]) {{
                    const docBtn = eventDivs[{event_index}].querySelector('button[aria-label*="document" i]');
                    return docBtn !== null;
                }}
                return false;
            }}
        ''')

        if not has_doc:
            return None

        # Click and download
        with page.expect_download(timeout=30000) as download_info:
            page.evaluate(f'''
                () => {{
                    const eventDivs = document.querySelectorAll('[ng-repeat*="event"]');
                    if (eventDivs[{event_index}]) {{
                        const docBtn = eventDivs[{event_index}].querySelector('button[aria-label*="document" i]');
                        if (docBtn) docBtn.click();
                    }}
                }}
            ''')

        download = download_info.value

        # Generate filename
        if event_type and event_date:
            # Clean filename
            clean_type = re.sub(r'[^\w\s-]', '', event_type)[:30]
            clean_date = event_date.replace('/', '-')
            filename = f"{clean_date}_{clean_type}.pdf"
        else:
            filename = download.suggested_filename or f"document_{event_index + 1}.pdf"

        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'

        file_path = download_path / filename
        download.save_as(str(file_path))

        # Save to database
        doc_date = None
        if event_date:
            try:
                doc_date = datetime.strptime(event_date, '%m/%d/%Y').date()
            except ValueError:
                pass

        with get_session() as session:
            document = Document(
                case_id=case_id,
                document_name=filename,
                file_path=str(file_path),
                document_date=doc_date
            )
            session.add(document)
            session.commit()

        logger.info(f"    Downloaded document: {filename}")
        return str(file_path)

    except Exception as e:
        logger.debug(f"    No document download for event {event_index}: {e}")
        return None


def download_upset_bid_documents(page: Page, case_id: int, county: str, case_number: str):
    """
    Download documents specifically for upset bid and sale events.

    This is a targeted download function for bid extraction. It:
    1. Finds events with "upset bid" or "report of sale" in the name
    2. Downloads only those documents (not all docs)
    3. Returns info about downloaded files for OCR processing

    Args:
        page: Playwright page object (on case detail page)
        case_id: Database ID of the case
        county: County name (e.g., 'wake')
        case_number: Case number (e.g., '24SP000437-910')

    Returns:
        list: List of dicts with downloaded document info:
            - file_path: Path to downloaded PDF
            - event_type: Type of event (e.g., "Upset Bid Filed")
            - event_date: Date string (MM/DD/YYYY)
    """
    logger.info(f"Checking for upset bid/sale documents...")

    download_path = config.get_pdf_path(county, case_number)
    downloaded = []

    try:
        # Find all events with their document button status
        # Use JavaScript to get event details with document availability
        events_with_docs = page.evaluate(r'''
            () => {
                const results = [];

                // Find all event containers (Angular ng-repeat)
                const eventDivs = document.querySelectorAll('[ng-repeat*="event"]');

                eventDivs.forEach((eventDiv, idx) => {
                    const text = eventDiv.textContent || '';
                    const textLower = text.toLowerCase();

                    // Check if this is an upset bid or sale event
                    const isUpsetBid = textLower.includes('upset bid');
                    const isSaleReport = textLower.includes('report of') && textLower.includes('sale');
                    const isNoticeOfSale = textLower.includes('notice of sale');

                    if (isUpsetBid || isSaleReport || isNoticeOfSale) {
                        // Check for document button/icon
                        const docBtn = eventDiv.querySelector('button[aria-label*="document" i]');
                        const docImg = eventDiv.querySelector('img[title*="document" i]');

                        if (docBtn || docImg) {
                            // Extract event date
                            const dateMatch = text.match(/(\d{2}\/\d{2}\/\d{4})/);
                            const eventDate = dateMatch ? dateMatch[1] : '';

                            // Extract event type - find capitalized text
                            let eventType = '';
                            const lines = text.split('\n').map(l => l.trim()).filter(l => l);
                            for (const line of lines) {
                                if (line.match(/^[A-Z][a-zA-Z\s()/\-0-9]+$/) &&
                                    line.length > 5 && line.length < 80) {
                                    eventType = line;
                                    break;
                                }
                            }

                            results.push({
                                index: idx,
                                eventType: eventType,
                                eventDate: eventDate,
                                hasButton: !!docBtn,
                                hasImage: !!docImg,
                                isUpsetBid: isUpsetBid,
                                isSale: isSaleReport || isNoticeOfSale
                            });
                        }
                    }
                });

                return results;
            }
        ''')

        if not events_with_docs:
            logger.info(f"  No upset bid/sale documents found")
            return []

        logger.info(f"  Found {len(events_with_docs)} upset bid/sale document(s)")

        for event_info in events_with_docs:
            event_index = event_info['index']
            event_type = event_info.get('eventType', 'Unknown')
            event_date = event_info.get('eventDate', '')

            logger.info(f"    Downloading: {event_date} - {event_type}")

            try:
                # Set up download handler
                with page.expect_download(timeout=30000) as download_info:
                    # Click the document button/image for this specific event
                    page.evaluate(f'''
                        () => {{
                            const eventDivs = document.querySelectorAll('[ng-repeat*="event"]');
                            const eventDiv = eventDivs[{event_index}];
                            if (eventDiv) {{
                                // Try button first, then image
                                const docBtn = eventDiv.querySelector('button[aria-label*="document" i]');
                                const docImg = eventDiv.querySelector('img[title*="document" i]');
                                if (docBtn) docBtn.click();
                                else if (docImg) docImg.click();
                            }}
                        }}
                    ''')

                download = download_info.value

                # Generate meaningful filename
                clean_type = re.sub(r'[^\w\s-]', '', event_type)[:40]
                clean_date = event_date.replace('/', '-') if event_date else 'unknown'
                filename = f"{clean_date}_{clean_type}.pdf"

                file_path = download_path / filename
                download.save_as(str(file_path))

                # Create database record
                doc_date = None
                if event_date:
                    try:
                        doc_date = datetime.strptime(event_date, '%m/%d/%Y').date()
                    except ValueError:
                        pass

                with get_session() as session:
                    document = Document(
                        case_id=case_id,
                        document_name=filename,
                        file_path=str(file_path),
                        document_date=doc_date
                    )
                    session.add(document)
                    session.commit()
                    doc_id = document.id

                downloaded.append({
                    'file_path': str(file_path),
                    'document_id': doc_id,
                    'event_type': event_type,
                    'event_date': event_date,
                    'is_upset_bid': event_info.get('isUpsetBid', False),
                    'is_sale': event_info.get('isSale', False)
                })

                logger.info(f"      Saved: {filename}")

            except Exception as e:
                logger.warning(f"      Download failed: {e}")

            # Small delay between downloads
            time.sleep(0.5)

    except Exception as e:
        logger.error(f"Error downloading upset bid documents: {e}")

    return downloaded


def download_all_case_documents(page: Page, case_id: int, county: str, case_number: str,
                                 skip_existing: bool = True):
    """
    Download ALL documents for a case with detailed event association.

    Unlike download_upset_bid_documents which is targeted, this downloads every
    document attached to every event. This is important for AI analysis which
    needs full context including:
    - Original mortgage/deed of trust info
    - Foreclosure filings
    - Sale reports
    - Upset bid notices
    - All other court filings

    Args:
        page: Playwright page object (on case detail page)
        case_id: Database ID of the case
        county: County name (e.g., 'wake')
        case_number: Case number (e.g., '24SP000437-910')
        skip_existing: If True, skip documents already in database

    Returns:
        list: List of dicts with downloaded document info:
            - file_path: Path to downloaded PDF
            - document_id: Database ID of the document record
            - event_type: Type of event this document is attached to
            - event_date: Date string (MM/DD/YYYY)
            - is_new: True if this was a new download, False if existing
    """
    logger.info(f"Downloading ALL documents for case...")

    download_path = config.get_pdf_path(county, case_number)
    downloaded = []

    # Get existing documents to avoid duplicates
    existing_docs = set()
    if skip_existing:
        with get_session() as session:
            docs = session.query(Document).filter_by(case_id=case_id).all()
            for doc in docs:
                # Use filename as identifier
                if doc.document_name:
                    existing_docs.add(doc.document_name)
                if doc.file_path:
                    existing_docs.add(Path(doc.file_path).name)

    try:
        # Find all events with their document button status
        # Use JavaScript to get ALL event details with document availability
        all_events_with_docs = page.evaluate(r'''
            () => {
                const results = [];

                // Find all event containers (Angular ng-repeat)
                const eventDivs = document.querySelectorAll('[ng-repeat*="event"]');

                eventDivs.forEach((eventDiv, idx) => {
                    const text = eventDiv.textContent || '';

                    // Check for document button/icon
                    const docBtn = eventDiv.querySelector('button[aria-label*="document" i]');
                    const docImg = eventDiv.querySelector('img[title*="document" i]');

                    if (docBtn || docImg) {
                        // Extract event date
                        const dateMatch = text.match(/(\d{2}\/\d{2}\/\d{4})/);
                        const eventDate = dateMatch ? dateMatch[1] : '';

                        // Extract event type - find capitalized text
                        let eventType = '';
                        const lines = text.split('\n').map(l => l.trim()).filter(l => l);
                        for (const line of lines) {
                            if (line.match(/^[A-Z][a-zA-Z\s()/\-0-9]+$/) &&
                                line.length > 5 && line.length < 80) {
                                eventType = line;
                                break;
                            }
                        }

                        // Categorize document type
                        const textLower = text.toLowerCase();
                        const isUpsetBid = textLower.includes('upset bid');
                        const isSaleReport = textLower.includes('report of') && textLower.includes('sale');
                        const isNoticeOfSale = textLower.includes('notice of sale');
                        const isForeclosureFiling = textLower.includes('foreclosure') ||
                                                     textLower.includes('deed of trust');
                        const isOrder = textLower.includes('order') || textLower.includes('findings');

                        results.push({
                            index: idx,
                            eventType: eventType,
                            eventDate: eventDate,
                            hasButton: !!docBtn,
                            hasImage: !!docImg,
                            isUpsetBid: isUpsetBid,
                            isSale: isSaleReport || isNoticeOfSale,
                            isForeclosureFiling: isForeclosureFiling,
                            isOrder: isOrder
                        });
                    }
                });

                return results;
            }
        ''')

        if not all_events_with_docs:
            logger.info(f"  No documents found on case page")
            return []

        logger.info(f"  Found {len(all_events_with_docs)} event(s) with documents")

        for event_info in all_events_with_docs:
            event_index = event_info['index']
            event_type = event_info.get('eventType', 'Unknown')
            event_date = event_info.get('eventDate', '')

            # Generate filename to check for duplicates
            clean_type = re.sub(r'[^\w\s-]', '', event_type)[:40]
            clean_date = event_date.replace('/', '-') if event_date else 'unknown'
            expected_filename = f"{clean_date}_{clean_type}.pdf"

            # Skip if we already have this document
            if skip_existing and expected_filename in existing_docs:
                logger.debug(f"    Skipping existing: {expected_filename}")
                downloaded.append({
                    'file_path': str(download_path / expected_filename),
                    'document_id': None,
                    'event_type': event_type,
                    'event_date': event_date,
                    'is_new': False,
                    'is_upset_bid': event_info.get('isUpsetBid', False),
                    'is_sale': event_info.get('isSale', False)
                })
                continue

            logger.info(f"    Downloading: {event_date} - {event_type}")

            try:
                # Set up download handler
                with page.expect_download(timeout=30000) as download_info:
                    # Click the document button/image for this specific event
                    page.evaluate(f'''
                        () => {{
                            const eventDivs = document.querySelectorAll('[ng-repeat*="event"]');
                            const eventDiv = eventDivs[{event_index}];
                            if (eventDiv) {{
                                // Try button first, then image
                                const docBtn = eventDiv.querySelector('button[aria-label*="document" i]');
                                const docImg = eventDiv.querySelector('img[title*="document" i]');
                                if (docBtn) docBtn.click();
                                else if (docImg) docImg.click();
                            }}
                        }}
                    ''')

                download = download_info.value

                # Generate meaningful filename
                filename = expected_filename
                file_path = download_path / filename

                # Handle duplicate filenames
                counter = 1
                while file_path.exists():
                    filename = f"{clean_date}_{clean_type}_{counter}.pdf"
                    file_path = download_path / filename
                    counter += 1

                download.save_as(str(file_path))

                # Create database record
                doc_date = None
                if event_date:
                    try:
                        doc_date = datetime.strptime(event_date, '%m/%d/%Y').date()
                    except ValueError:
                        pass

                with get_session() as session:
                    document = Document(
                        case_id=case_id,
                        document_name=filename,
                        file_path=str(file_path),
                        document_date=doc_date
                    )
                    session.add(document)
                    session.commit()
                    doc_id = document.id

                downloaded.append({
                    'file_path': str(file_path),
                    'document_id': doc_id,
                    'event_type': event_type,
                    'event_date': event_date,
                    'is_new': True,
                    'is_upset_bid': event_info.get('isUpsetBid', False),
                    'is_sale': event_info.get('isSale', False)
                })

                logger.info(f"      Saved: {filename}")

            except Exception as e:
                logger.warning(f"      Download failed: {e}")

            # Small delay between downloads
            time.sleep(0.5)

        new_count = sum(1 for d in downloaded if d.get('is_new'))
        logger.info(f"  Downloaded {new_count} new documents, {len(downloaded) - new_count} existing")

    except Exception as e:
        logger.error(f"Error downloading all case documents: {e}")

    return downloaded
