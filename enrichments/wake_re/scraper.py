"""Page scraping for Wake County Real Estate portal."""

import re
import logging
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from enrichments.wake_re.url_builder import (
    build_pinlist_url,
    build_validate_address_url,
)


logger = logging.getLogger(__name__)

# Request settings
REQUEST_TIMEOUT = 30
MAX_RETRIES = 1
RETRY_DELAY = 2


def _fetch_with_retry(url: str) -> str:
    """
    Fetch URL with retry logic.

    Args:
        url: URL to fetch

    Returns:
        HTML content

    Raises:
        requests.RequestException: If all retries fail
    """
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            last_error = e
            if attempt < MAX_RETRIES:
                logger.warning(f"Fetch attempt {attempt + 1} failed: {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))

    raise last_error


def parse_pinlist_html(html: str) -> List[Dict[str, str]]:
    """
    Parse PinList results page.

    Args:
        html: Raw HTML from PinList.asp

    Returns:
        List of dicts with account_id and other fields
    """
    results = []
    soup = BeautifulSoup(html, 'html.parser')

    # Find all account links
    account_pattern = re.compile(r'Account\.asp\?id=(\d+)')

    for link in soup.find_all('a', href=account_pattern):
        match = account_pattern.search(link.get('href', ''))
        if match:
            results.append({
                'account_id': match.group(1),
                'link_text': link.get_text(strip=True),
            })

    return results


def parse_validate_address_html(html: str) -> List[Dict[str, str]]:
    """
    Parse ValidateAddress results page.

    Expects table with columns:
    Line | Account | St Num | St Misc | Pfx | Street Name | Type | Sfx | ETJ | Owner

    Args:
        html: Raw HTML from ValidateAddress.asp

    Returns:
        List of dicts with parsed row data
    """
    results = []
    soup = BeautifulSoup(html, 'html.parser')

    # Find account links and their parent rows
    account_pattern = re.compile(r'Account\.asp\?id=(\d+)')

    for link in soup.find_all('a', href=account_pattern):
        match = account_pattern.search(link.get('href', ''))
        if not match:
            continue

        account_id = match.group(1)

        # Find parent row
        row = link.find_parent('tr')
        if not row:
            continue

        cells = row.find_all('td')
        if len(cells) < 9:
            continue

        # Parse based on expected column order
        # Line(0) | Account(1) | St Num(2) | St Misc(3) | Pfx(4) | Street Name(5) | Type(6) | Sfx(7) | ETJ(8) | Owner(9)
        try:
            result = {
                'account_id': account_id,
                'stnum': cells[2].get_text(strip=True),
                'st_misc': cells[3].get_text(strip=True),
                'prefix': cells[4].get_text(strip=True),
                'street_name': cells[5].get_text(strip=True),
                'street_type': cells[6].get_text(strip=True),
                'suffix': cells[7].get_text(strip=True),
                'etj': cells[8].get_text(strip=True),
            }
            if len(cells) > 9:
                result['owner'] = cells[9].get_text(strip=True)
            results.append(result)
        except (IndexError, AttributeError) as e:
            logger.warning(f"Failed to parse row: {e}")
            continue

    return results


def match_address_result(
    results: List[Dict[str, str]],
    stnum: str,
    prefix: Optional[str],
    name: str,
    etj: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """
    Find single matching result from ValidateAddress output.

    Args:
        results: Parsed results from parse_validate_address_html
        stnum: Street number to match
        prefix: Directional prefix (N/S/E/W) or None
        name: Street name (uppercase)
        etj: City code (optional)

    Returns:
        Single matching row or None
    """
    matches = []

    for row in results:
        # Match street number
        if row.get('stnum') != stnum:
            continue

        # Match prefix (empty string or None both mean no prefix)
        row_prefix = row.get('prefix', '').strip()
        search_prefix = (prefix or '').strip()
        if row_prefix.upper() != search_prefix.upper():
            continue

        # Match street name
        if row.get('street_name', '').upper() != name.upper():
            continue

        # Match ETJ if provided
        if etj and row.get('etj', '').upper() != etj.upper():
            continue

        matches.append(row)

    # Only return if exactly one match
    if len(matches) == 1:
        return matches[0]

    return None


def fetch_pinlist_results(parcel_id: str) -> List[Dict[str, str]]:
    """
    Fetch and parse PinList results for a parcel ID.

    Args:
        parcel_id: 10-digit Wake County parcel ID

    Returns:
        List of account results

    Raises:
        requests.RequestException: On network error
    """
    url = build_pinlist_url(parcel_id)
    if not url:
        return []

    logger.debug(f"Fetching PinList: {url}")
    html = _fetch_with_retry(url)
    return parse_pinlist_html(html)


def fetch_validate_address_results(stnum: str, stname: str) -> List[Dict[str, str]]:
    """
    Fetch and parse ValidateAddress results.

    Args:
        stnum: Street number
        stname: Street name (without type suffix)

    Returns:
        List of address match results

    Raises:
        requests.RequestException: On network error
    """
    url = build_validate_address_url(stnum, stname)

    logger.debug(f"Fetching ValidateAddress: {url}")
    html = _fetch_with_retry(url)
    return parse_validate_address_html(html)
