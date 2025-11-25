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

    Per project requirements, foreclosure cases are identified from the case detail page by:
    1. Case Type in Case Information section reads "Foreclosure (Special Proceeding)"
    2. Case Events contain foreclosure-related events like:
       - "Foreclosure (Special Proceeding) Notice of Hearing"
       - "Findings And Order Of Foreclosure"
       - "Foreclosure Case Initiated"
       - "Report Of Foreclosure Sale (Chapter 45)"
       - "Notice Of Sale/Resale"
       - "Upset Bid Filed"

    Args:
        case_data: Dictionary containing case information from case detail page

    Returns:
        bool: True if case is a foreclosure
    """
    # Check case type - must contain "foreclosure"
    case_type = (case_data.get('case_type') or '').lower()
    if 'foreclosure' in case_type:
        logger.debug(f"Foreclosure identified by case type: {case_type}")
        return True

    # Check events for foreclosure indicators
    events = case_data.get('events') or []
    for event in events:
        event_type = (event.get('event_type') or '').lower()
        for indicator in FORECLOSURE_EVENT_INDICATORS:
            if indicator in event_type:
                logger.debug(f"Foreclosure identified by event: {event_type}")
                return True

    return False


def parse_search_results(page_content):
    """
    Parse search results page to extract case information.

    The portal search results page has a table with columns:
    - Case Number (with link)
    - Style / Defendant (contains case type like "Foreclosure - ..." or "Motor Vehicle Lien - ...")
    - Status
    - Location
    - Party Name
    - Party Type

    Portal uses Kendo UI Grid with structure:
    - Grid container: #CasesGrid or table with Cases heading
    - Rows: tbody tr or tr.k-master-row
    - Case links: a.caseLink with data-url attribute, or regular links

    Args:
        page_content: HTML content of search results page

    Returns:
        dict: {
            'cases': [{'case_number': str, 'case_url': str, 'style': str, 'status': str}, ...],
            'total_count': int
        }
    """
    soup = BeautifulSoup(page_content, 'html.parser')
    cases = []

    # Method 1: Try Kendo UI Grid rows
    rows = soup.select('#CasesGrid tbody tr.k-master-row')

    # Method 2: If no Kendo grid, look for regular table rows
    if not rows:
        # Look for table with case data
        tables = soup.find_all('table')
        for table in tables:
            header_row = table.find('tr')
            if header_row:
                headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
                if 'case number' in ' '.join(headers):
                    rows = table.find_all('tr')[1:]  # Skip header row
                    break

    for row in rows:
        cells = row.find_all(['td', 'gridcell'])

        # Extract case link
        case_link = row.select_one('a.caseLink') or row.select_one('a[href*="Case"]') or row.find('a')
        if case_link:
            case_number = case_link.text.strip()
            # Kendo stores URL in data-url attribute, not href
            case_url = case_link.get('data-url', '') or case_link.get('href', '')

            # Make URL absolute
            if case_url and not case_url.startswith('http') and case_url != '#':
                base_url = 'https://portal-nc.tylertech.cloud'
                case_url = f"{base_url}{case_url}"

            # Extract style from second column (Style / Defendant)
            style = None
            if len(cells) >= 2:
                style = cells[1].get_text(strip=True)

            # Extract status from third column
            status = None
            if len(cells) >= 3:
                status = cells[2].get_text(strip=True)

            if case_number:
                case_info = {
                    'case_number': case_number,
                    'case_url': case_url if case_url and case_url != '#' else None,
                    'style': style,
                    'status': status
                }
                cases.append(case_info)
                logger.debug(f"Found case: {case_number}, style: {style}")

    logger.info(f"Parsed {len(cases)} cases from search results")

    return {
        'cases': cases,
        'total_count': len(cases)
    }


def parse_case_detail(page_content):
    """
    Parse case detail page (Register of Actions) to extract all case information.

    The NC Courts Portal uses an Angular "Register of Actions" (ROA) page with:
    - table.roa-caseinfo-info-rows: Contains Case Type and Case Status
    - Case Summary section with style (e.g., "FORECLOSURE- Name") and Filed on date
    - Case Events section with event listings

    For foreclosure identification:
    - Case Type = "Foreclosure (Special Proceeding)"
    - OR events contain foreclosure indicators

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
        'style': None,
        'property_address': None,
        'parties': [],
        'events': [],
        'documents': []
    }

    # Method 1: Parse ROA Case Information table (class="roa-caseinfo-info-rows")
    # This table has "Case Type:" and "Case Status:" rows
    roa_table = soup.find('table', class_='roa-caseinfo-info-rows')
    if roa_table:
        rows = roa_table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)

                if 'case type' in label:
                    case_data['case_type'] = value
                    logger.debug(f"Case type: {value}")
                elif 'case status' in label:
                    case_data['case_status'] = value
                    logger.debug(f"Case status: {value}")

    # Method 2: Fallback - search all tables for Case Type/Status
    if not case_data['case_type']:
        all_tables = soup.find_all('table')
        for table in all_tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)

                    if 'case type' in label and not case_data['case_type']:
                        case_data['case_type'] = value
                        logger.debug(f"Case type (fallback): {value}")
                    elif 'case status' in label and not case_data['case_status']:
                        case_data['case_status'] = value
                        logger.debug(f"Case status (fallback): {value}")

    # Method 3: Extract file date from "Filed on:" text
    # The ROA page has "Filed on:" followed by a date
    page_text = soup.get_text()
    filed_match = re.search(r'Filed on:\s*(\d{2}/\d{2}/\d{4})', page_text)
    if filed_match:
        case_data['file_date'] = filed_match.group(1)
        logger.debug(f"File date: {case_data['file_date']}")

    # Method 4: Check for foreclosure indicators in the full page text
    # This is a backup method to identify foreclosures even if parsing fails
    page_text_lower = page_text.lower()
    foreclosure_text_indicators = [
        'foreclosure (special proceeding)',
        'foreclosure case initiated',
        'findings and order of foreclosure',
        'report of foreclosure sale',
        'notice of sale/resale',
        'upset bid filed',
        'notice of foreclosure'
    ]

    # Extract events from page text using patterns
    # Events have format: DATE followed by event type text
    # Look for common event types
    event_patterns = [
        r'(\d{2}/\d{2}/\d{4})\s*(?:.*?)(Foreclosure[^§\n]*)',
        r'(\d{2}/\d{2}/\d{4})\s*(?:.*?)(Notice Of Sale/Resale[^§\n]*)',
        r'(\d{2}/\d{2}/\d{4})\s*(?:.*?)(Report Of Foreclosure Sale[^§\n]*)',
        r'(\d{2}/\d{2}/\d{4})\s*(?:.*?)(Findings And Order Of Foreclosure[^§\n]*)',
        r'(\d{2}/\d{2}/\d{4})\s*(?:.*?)(Upset Bid[^§\n]*)',
    ]

    for indicator in foreclosure_text_indicators:
        if indicator in page_text_lower:
            # Add as a pseudo-event for foreclosure detection
            case_data['events'].append({
                'event_date': None,
                'event_type': indicator,
                'event_description': f'Found in page: {indicator}'
            })
            logger.debug(f"Found foreclosure indicator in text: {indicator}")

    logger.info(f"Parsed case - Type: {case_data['case_type']}, Events: {len(case_data['events'])}")

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
