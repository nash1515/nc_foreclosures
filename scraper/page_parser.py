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
    'upset bid filed',
    # NOTE: SCRA removed - it's required in many non-foreclosure proceedings
    # (incompetency, guardianship, adoption, etc.) and causes false positives
]

# Event types that indicate an upset bid opportunity (includes non-foreclosure sales like partitions)
# These catch cases where Case Type is "Special Proceeding" but there's a sale with upset bid rights
UPSET_BID_OPPORTUNITY_INDICATORS = [
    'upset bid filed',
    'report of sale',  # Generic report of sale (partition sales, etc.)
    'order allowing partition by',  # Partition by sale orders
    'partition by sale',
]

# Document title patterns that indicate a potential sale with upset bid rights
# These are checked against document titles (not event types) for day-1 detection
SALE_DOCUMENT_INDICATORS = [
    'petition to sell',
    'petition for sale',  # Matches "PETITION FOR THE SALE OF REAL PROPERTY"
    'petition to lease',
    'petition to mortgage',
    'petition for partition',  # Partition of real property - leads to sale
    "ward's estate",
    "incompetent's estate",
    "minor's estate",
    "decedent's estate",
    'sell real property',
    'sale of real property',  # Matches "PETITION FOR THE SALE OF REAL PROPERTY"
    'tax lien foreclosure',
    'tax foreclosure',
    'delinquent tax',
    'receivership',
    "receiver's sale",
    'trust property sale',
    'sell trust property',
    # Estate administration (leads to property sales)
    'estate administration',
    'administration of estate',
    'personal representative',
    # Property-related proceedings
    'quiet title',
    'condemnation',
    'eminent domain',
    'claim and delivery',
]

# Event types that indicate NON-property cases (skip these)
NON_PROPERTY_INDICATORS = [
    'adoption',
    'name change',
    'motor vehicle',
    'incompetent driver',
    'incompetency',
    'guardianship',
]


def is_foreclosure_case(case_data):
    """
    Determine if a case is a foreclosure OR upset bid opportunity.

    This function identifies cases we want to track, including:
    1. Traditional foreclosures (Case Type contains "Foreclosure")
    2. Cases with foreclosure-related events
    3. Non-foreclosure sales with upset bid opportunities (e.g., partition sales)
       - These have Case Type "Special Proceeding" but contain "Report of Sale" or "Upset Bid Filed"

    Args:
        case_data: Dictionary containing case information from case detail page

    Returns:
        bool: True if case is a foreclosure or upset bid opportunity
    """
    # Get events for checking
    events = case_data.get('events') or []
    case_type = (case_data.get('case_type') or '').lower()

    # Check case_type for non-property indicators FIRST (exclusions)
    # This catches cases like "Incompetency" before checking events
    for indicator in NON_PROPERTY_INDICATORS:
        if indicator in case_type:
            logger.debug(f"Non-property case identified by case type: {case_type}")
            return False

    # Check events for non-property indicators (exclusions)
    for event in events:
        event_type = (event.get('event_type') or '').lower()
        for indicator in NON_PROPERTY_INDICATORS:
            if indicator in event_type:
                logger.debug(f"Non-property case identified by event type: {event_type}")
                return False

    # Check case type - must contain "foreclosure"
    if 'foreclosure' in case_type:
        logger.debug(f"Foreclosure identified by case type: {case_type}")
        return True

    # Check events for foreclosure indicators
    for event in events:
        event_type = (event.get('event_type') or '').lower()
        for indicator in FORECLOSURE_EVENT_INDICATORS:
            if indicator in event_type:
                logger.debug(f"Foreclosure identified by event: {event_type}")
                return True

    # Check for non-foreclosure upset bid opportunities (partition sales, etc.)
    for event in events:
        event_type = (event.get('event_type') or '').lower()
        for indicator in UPSET_BID_OPPORTUNITY_INDICATORS:
            if indicator in event_type:
                logger.debug(f"Upset bid opportunity identified by event: {event_type}")
                return True

    # Check document titles for sale indicators (for day-1 detection)
    for event in events:
        document_title = (event.get('document_title') or '').lower()
        if document_title:
            for indicator in SALE_DOCUMENT_INDICATORS:
                if indicator in document_title:
                    logger.debug(f"Sale opportunity identified by document title: {document_title}")
                    return True

    # Also check event_type for sale indicators (e.g., "Petition To Sell")
    for event in events:
        event_type = (event.get('event_type') or '').lower()
        if event_type:
            # Exclude motor vehicle sales
            if 'motor vehicle' in event_type:
                continue
            for indicator in SALE_DOCUMENT_INDICATORS:
                if indicator in event_type:
                    logger.debug(f"Sale opportunity identified by event type: {event_type}")
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

            # Extract location from fourth column (County)
            location = None
            if len(cells) >= 4:
                location = cells[3].get_text(strip=True)

            if case_number:
                case_info = {
                    'case_number': case_number,
                    'case_url': case_url if case_url and case_url != '#' else None,
                    'style': style,
                    'status': status,
                    'location': location  # County name from search results
                }
                cases.append(case_info)
                logger.debug(f"Found case: {case_number}, style: {style}, location: {location}")

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
    - Party Information table with respondents, petitioners, trustees
    - Case Events section with event listings, dates, and document links
    - Hearings section with scheduled hearing dates

    Args:
        page_content: HTML content of case detail page

    Returns:
        dict: Case data including case info, parties, events, hearings, documents
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
        'hearings': [],
        'documents': []
    }

    page_text = soup.get_text()

    # ========== 1. CASE TYPE AND STATUS ==========
    # Parse ROA Case Information table (class="roa-caseinfo-info-rows")
    # Note: Labels use &nbsp; (non-breaking space U+00A0) which must be normalized
    roa_table = soup.find('table', class_='roa-caseinfo-info-rows')
    if roa_table:
        logger.debug("Found ROA table with class 'roa-caseinfo-info-rows'")
        rows = roa_table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).replace('\xa0', ' ').lower()
                value = cells[1].get_text(strip=True).replace('\xa0', ' ')

                if 'case type' in label:
                    case_data['case_type'] = value
                    logger.debug(f"Case type: {value}")
                elif 'case status' in label:
                    case_data['case_status'] = value
                    logger.debug(f"Case status: {value}")

    # ========== 2. STYLE (Case Title) ==========
    # Look for the case title like "FORECLOSURE (HOA) - Mark Dwayne Ellis"
    # It's in a div within the Case Summary section
    style_match = re.search(r'(FORECLOSURE[^§\n]{3,100})', page_text)
    if style_match:
        style_text = style_match.group(1).strip()
        # Clean up the style - remove extra whitespace
        style_text = ' '.join(style_text.split())
        if len(style_text) < 150:  # Sanity check
            case_data['style'] = style_text
            logger.debug(f"Style: {style_text}")

    # ========== 3. FILE DATE ==========
    filed_match = re.search(r'Filed on:\s*(\d{2}/\d{2}/\d{4})', page_text)
    if filed_match:
        case_data['file_date'] = filed_match.group(1)
        logger.debug(f"File date: {case_data['file_date']}")

    # ========== 4. PARTIES ==========
    # Party Information is in a table with class "roa-table td-pad-5"
    # Structure: Respondent | Name | (empty)
    party_table = soup.find('table', class_=lambda c: c and 'roa-table' in c and 'td-pad-5' in c)
    if party_table:
        party_rows = party_table.find_all('tr')
        for row in party_rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                party_type = cells[0].get_text(strip=True).replace('\xa0', ' ')
                party_name = cells[1].get_text(strip=True).replace('\xa0', ' ')

                # Validate this looks like a party row
                valid_party_types = ['Respondent', 'Petitioner', 'Trustee', 'Plaintiff', 'Defendant',
                                    'Garnishee', 'Applicant', 'Attorney', 'Guardian']
                if party_type and party_name and any(pt in party_type for pt in valid_party_types):
                    case_data['parties'].append({
                        'party_type': party_type,
                        'party_name': party_name
                    })
                    logger.debug(f"Party: {party_type} - {party_name}")

    # ========== 5. EVENTS ==========
    # Events are in divs with ng-repeat="event in ..." attribute
    # Each event has: date, type, filed by, against, hearing date/time, document link
    event_divs = soup.find_all(attrs={'ng-repeat': lambda v: v and 'event' in v.lower()}) if soup.find_all(attrs={'ng-repeat': True}) else []

    for event_div in event_divs:
        event_text = event_div.get_text()

        # Extract event date (first date in the block)
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', event_text)
        event_date = date_match.group(1) if date_match else None

        # Extract event type - look for capitalized text that's an event description
        event_type = None
        event_description = None
        lines = [l.strip() for l in event_text.split('\n') if l.strip()]
        event_type_index = None
        for i, line in enumerate(lines):
            # Event types are usually capitalized phrases
            # Allow letters, spaces, parens, numbers, slashes, hyphens (for types like "Chapter 45", "Sale/Resale")
            if (re.match(r'^[A-Z][a-zA-Z\s()/\-0-9]+$', line) and
                5 < len(line) < 100 and
                not any(skip in line for skip in ['Index', 'Created', 'Filed By', 'Against'])):
                event_type = line
                event_type_index = i
                break

        # Extract event description - the line(s) after event type that contain details
        # Examples: "1508 Beacon Village Drive, Raleigh 27604" for Report of Sale
        #           "Petition for Possession..." for Petition To Sell
        if event_type_index is not None:
            skip_labels = ['Index', 'Created', 'Filed By', 'Against', 'A document is available',
                          'Click here', 'document', 'Index #']
            desc_lines = []
            for line in lines[event_type_index + 1:]:
                # Stop at form labels or metadata
                if any(skip in line for skip in skip_labels):
                    break
                # Skip dates that look like Created dates (MM/DD/YYYY format followed by time)
                if re.match(r'^\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}', line):
                    break
                # Skip pure dates
                if re.match(r'^\d{2}/\d{2}/\d{4}$', line):
                    continue
                # Capture substantive description lines
                if len(line) > 3 and len(line) < 500:
                    desc_lines.append(line)
                    # Usually just one or two lines of description
                    if len(desc_lines) >= 2:
                        break
            if desc_lines:
                event_description = ' '.join(desc_lines)

        # Extract Index number
        index_match = re.search(r'Index\s*#\s*(\d+)', event_text)

        # Extract Filed By and Against
        filed_by_match = re.search(r'Filed By:\s*([^§\n]+)', event_text)
        against_match = re.search(r'Against:\s*([^§\n]+)', event_text)

        # Extract hearing date/time if present
        hearing_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})', event_text)

        # Check for document link
        doc_button = event_div.find('button', attrs={'aria-label': lambda v: v and 'document' in v.lower()}) if event_div.find('button') else None
        has_document = doc_button is not None

        # Extract document title (text on clickable document link)
        document_title = None
        doc_link = event_div.find('a') or event_div.find('button', attrs={'aria-label': lambda v: v and 'document' in v.lower()})
        if doc_link:
            # Get text near the document link - usually the document title
            doc_text = doc_link.get_text(strip=True) if doc_link else None
            if not doc_text or doc_text == 'Click here to view the document':
                # Look for text in sibling or parent elements
                parent = doc_link.parent
                if parent:
                    # Get all text in the parent, excluding common labels
                    parent_text = parent.get_text(' ', strip=True)
                    # Extract document title - usually after "A document is available"
                    for line in parent_text.split('\n'):
                        line = line.strip()
                        if line and 'document is available' not in line.lower() and 'click here' not in line.lower():
                            if 5 < len(line) < 200 and not line.startswith('Index') and not line.startswith('Created'):
                                document_title = line
                                break
            else:
                document_title = doc_text

        if event_date or event_type:
            event_data = {
                'event_date': event_date,
                'event_type': event_type,
                'event_description': event_description,
                'document_title': document_title,  # Document title for classification
                'filed_by': filed_by_match.group(1).strip() if filed_by_match else None,
                'filed_against': against_match.group(1).strip() if against_match else None,
                'hearing_date': f"{hearing_match.group(1)} {hearing_match.group(2)}" if hearing_match else None,
                'document_url': None,  # Will need JS execution to get actual URL
                'has_document': has_document
            }
            case_data['events'].append(event_data)
            logger.debug(f"Event: {event_date} - {event_type} - Doc: {document_title}")

    # ========== 6. HEARINGS ==========
    # Hearings are in a separate section with ng-repeat="hearing in ..."
    hearing_divs = soup.find_all(attrs={'ng-repeat': lambda v: v and 'hearing' in v.lower()}) if soup.find_all(attrs={'ng-repeat': True}) else []

    for hearing_div in hearing_divs:
        hearing_text = hearing_div.get_text()

        # Extract hearing date
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', hearing_text)

        # Extract time (usually in parentheses like "(2:30 PM)")
        time_match = re.search(r'\((\d{1,2}:\d{2}\s*(?:AM|PM)?)\)', hearing_text, re.IGNORECASE)

        # Extract hearing type
        hearing_type = None
        lines = [l.strip() for l in hearing_text.split('\n') if l.strip()]
        for line in lines:
            if not re.match(r'^\d', line) and 'Created' not in line and len(line) < 50:
                # Remove time in parentheses
                clean_line = re.sub(r'\([^)]+\)', '', line).strip()
                if clean_line:
                    hearing_type = clean_line
                    break

        if date_match:
            case_data['hearings'].append({
                'hearing_date': date_match.group(1),
                'hearing_time': time_match.group(1) if time_match else None,
                'hearing_type': hearing_type
            })
            logger.debug(f"Hearing: {date_match.group(1)} - {hearing_type}")

    # ========== 7. FALLBACK: Text-based foreclosure detection ==========
    # If structured parsing didn't find events, fall back to text search
    if not case_data['events']:
        page_text_lower = page_text.lower()
        foreclosure_indicators = [
            'foreclosure (special proceeding)',
            'foreclosure case initiated',
            'findings and order of foreclosure',
            'report of foreclosure sale',
            'notice of sale/resale',
            'upset bid filed'
        ]

        for indicator in foreclosure_indicators:
            if indicator in page_text_lower:
                case_data['events'].append({
                    'event_date': None,
                    'event_type': indicator,
                    'event_description': f'Found in page text: {indicator}',
                    'filed_by': None,
                    'filed_against': None,
                    'hearing_date': None,
                    'document_url': None,
                    'has_document': False
                })
                logger.debug(f"Found foreclosure indicator in text: {indicator}")

    logger.info(f"Parsed case - Type: {case_data['case_type']}, Style: {case_data['style']}, "
                f"Parties: {len(case_data['parties'])}, Events: {len(case_data['events'])}, "
                f"Hearings: {len(case_data['hearings'])}")

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
