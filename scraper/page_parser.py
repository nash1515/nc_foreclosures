"""HTML parsing utilities for NC Courts Portal."""

import re
from bs4 import BeautifulSoup
from common.logger import setup_logger
from scraper.portal_selectors import PORTAL_URL

logger = setup_logger(__name__)

# Event types that indicate a foreclosure case
FORECLOSURE_EVENT_INDICATORS = [
    'foreclosure (special proceeding)',
    'foreclosure (special proceeding) notice of hearing',
    'findings and order of foreclosure',
    'foreclosure case initiated',
    'report of foreclosure sale (chapter 45)',
    'notice of sale/resale',
    'upset bid filed'
]


def is_foreclosure_case(case_data):
    """
    Determine if a case is a foreclosure case.

    Checks both case type and event types for foreclosure indicators.

    Args:
        case_data: Dictionary containing case information

    Returns:
        bool: True if case is a foreclosure
    """
    # Check case type
    case_type = case_data.get('case_type', '').lower()
    if 'foreclosure' in case_type and 'special proceeding' in case_type:
        logger.debug(f"Foreclosure identified by case type: {case_type}")
        return True

    # Check events
    events = case_data.get('events', [])
    for event in events:
        event_type = event.get('event_type', '').lower()
        for indicator in FORECLOSURE_EVENT_INDICATORS:
            if indicator in event_type:
                logger.debug(f"Foreclosure identified by event: {event_type}")
                return True

    return False


def parse_search_results(page_content):
    """
    Parse search results page to extract case information.

    Portal uses Kendo UI Grid with structure:
    - Grid container: #CasesGrid
    - Rows: tbody tr.k-master-row
    - Case links: a.caseLink with data-url attribute

    Args:
        page_content: HTML content of search results page

    Returns:
        dict: {
            'cases': [{'case_number': str, 'case_url': str}, ...],
            'total_count': int
        }
    """
    soup = BeautifulSoup(page_content, 'html.parser')
    cases = []

    # Kendo UI Grid rows (not simple table)
    rows = soup.select('#CasesGrid tbody tr.k-master-row')

    for row in rows:
        # Extract case link from Kendo grid row
        case_link = row.select_one('a.caseLink')
        if case_link:
            case_number = case_link.text.strip()
            # Kendo stores URL in data-url attribute, not href
            case_url = case_link.get('data-url', '')

            # Make URL absolute
            if case_url and not case_url.startswith('http'):
                base_url = 'https://portal-nc.tylertech.cloud'
                case_url = f"{base_url}{case_url}"

            if case_number and case_url:
                cases.append({
                    'case_number': case_number,
                    'case_url': case_url
                })
                logger.debug(f"Found case: {case_number}")

    logger.info(f"Parsed {len(cases)} cases from search results")

    return {
        'cases': cases,
        'total_count': len(cases)
    }


def parse_case_detail(page_content):
    """
    Parse case detail page to extract all case information.

    Args:
        page_content: HTML content of case detail page

    Returns:
        dict: Case data including case info, events, documents
    """
    soup = BeautifulSoup(page_content, 'html.parser')

    case_data = {
        'case_type': None,
        'case_status': None,
        'file_date': None,
        'property_address': None,
        'events': [],
        'documents': []
    }

    # Parse case information section
    # The portal typically has a table with labels and values
    info_container = soup.select_one('#CaseInformationContainer')
    if info_container:
        info_rows = info_container.select('tr')
        for row in info_rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                label = cells[0].text.strip().lower()
                value = cells[1].text.strip()

                if 'case type' in label:
                    case_data['case_type'] = value
                    logger.debug(f"Case type: {value}")
                elif 'status' in label and 'case' in label:
                    case_data['case_status'] = value
                    logger.debug(f"Case status: {value}")
                elif 'file date' in label or 'filed date' in label:
                    case_data['file_date'] = value
                    logger.debug(f"File date: {value}")

    # Parse events table
    events_table = soup.select_one('#EventsTable')
    if events_table:
        event_rows = events_table.select('tbody tr')
        for row in event_rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                event_date = cells[0].text.strip() if cells[0] else None
                event_desc = cells[1].text.strip() if cells[1] else None

                if event_date and event_desc:
                    case_data['events'].append({
                        'event_date': event_date,
                        'event_type': event_desc,
                        'event_description': event_desc
                    })

        logger.debug(f"Parsed {len(case_data['events'])} events")

    # Parse documents table (for Phase 2)
    documents_table = soup.select_one('#DocumentsTable')
    if documents_table:
        doc_rows = documents_table.select('tbody tr')
        for row in doc_rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                doc_link = row.select_one('a')
                if doc_link:
                    doc_name = doc_link.text.strip()
                    doc_url = doc_link.get('href', '')

                    if doc_url and not doc_url.startswith('http'):
                        base_url = '/'.join(PORTAL_URL.split('/')[:3])
                        doc_url = f"{base_url}{doc_url}"

                    case_data['documents'].append({
                        'document_name': doc_name,
                        'document_url': doc_url
                    })

        logger.debug(f"Parsed {len(case_data['documents'])} documents")

    return case_data


def extract_total_count(page_content):
    """
    Extract total case count from search results.

    Kendo UI Grid displays pager info in .k-pager-info element.
    Format: "1 - 10 of 75 items"

    Args:
        page_content: HTML content of search results page

    Returns:
        int: Total number of cases, or None if not found
    """
    soup = BeautifulSoup(page_content, 'html.parser')

    # Kendo pager info element
    pager_info = soup.select_one('.k-pager-info')
    if pager_info:
        text = pager_info.text.strip()
        logger.debug(f"Kendo pager info: {text}")

        # Parse "1 - 10 of 75 items"
        match = re.search(r'of\s+(\d+)\s+items?', text, re.IGNORECASE)
        if match:
            total = int(match.group(1))
            logger.info(f"Total count extracted: {total}")
            return total

    logger.warning("Could not extract total count from Kendo pager")
    return None
