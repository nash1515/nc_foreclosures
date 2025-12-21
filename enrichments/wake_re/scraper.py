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
    build_address_search_url,
)
from enrichments.wake_re.config import ADDRESS_SEARCH_POST_URL


logger = logging.getLogger(__name__)

# Request settings
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
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

    # Return if exactly one match
    if len(matches) == 1:
        return matches[0]

    # If multiple matches, check if they all have the same account_id
    # (e.g., condos where 834 and 834-3D are same property)
    if len(matches) > 1:
        account_ids = set(m.get('account_id') for m in matches)
        if len(account_ids) == 1:
            logger.debug(f"Multiple rows ({len(matches)}) but same account_id, returning first match")
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


def parse_address_search_streets(html: str) -> List[Dict[str, str]]:
    """
    Parse AddressSearch street selection page.

    Returns list of streets with their locid values for checkbox selection.
    Each row has: Checkbox | Pfx | Street Name | St Type | Sfx | ETJ | Low Num | High Num

    Args:
        html: Raw HTML from AddressSearch.asp

    Returns:
        List of dicts with street info and locid
    """
    results = []
    soup = BeautifulSoup(html, 'html.parser')

    # Find all checkboxes (name is 'c1' with value being the locid)
    for checkbox in soup.find_all('input', {'type': 'checkbox'}):
        locid = checkbox.get('value')
        if not locid:
            continue

        # Find parent row
        row = checkbox.find_parent('tr')
        if not row:
            continue

        cells = row.find_all('td')
        if len(cells) < 7:
            continue

        # Parse based on expected column order
        # Checkbox(0) | Pfx(1) | Street Name(2) | St Type(3) | Sfx(4) | ETJ(5) | Low Num(6) | High Num(7)
        try:
            result = {
                'locid': locid,
                'prefix': cells[1].get_text(strip=True),
                'street_name': cells[2].get_text(strip=True),
                'street_type': cells[3].get_text(strip=True),
                'suffix': cells[4].get_text(strip=True),
                'etj': cells[5].get_text(strip=True),
                'low_num': cells[6].get_text(strip=True) if len(cells) > 6 else '',
                'high_num': cells[7].get_text(strip=True) if len(cells) > 7 else '',
            }
            results.append(result)
        except (IndexError, AttributeError) as e:
            logger.warning(f"Failed to parse street row: {e}")
            continue

    return results


def find_matching_street(
    streets: List[Dict[str, str]],
    prefix: str,
    street_name: str,
    stnum: str,
) -> Optional[Dict[str, str]]:
    """
    Find the street matching our search criteria.

    Args:
        streets: List of street options from parse_address_search_streets
        prefix: Directional prefix to match (N/S/E/W/NE/NW/SE/SW)
        street_name: Street name to match
        stnum: Street number (to verify it's in range)

    Returns:
        Matching street dict or None
    """
    stnum_int = int(stnum) if stnum.isdigit() else 0

    for street in streets:
        # Match prefix
        if street.get('prefix', '').upper() != prefix.upper():
            continue

        # Match street name
        if street.get('street_name', '').upper() != street_name.upper():
            continue

        # Verify street number is in range (if range is provided)
        low = street.get('low_num', '')
        high = street.get('high_num', '')
        if low and high and stnum_int:
            try:
                low_int = int(low)
                high_int = int(high)
                if not (low_int <= stnum_int <= high_int):
                    continue
            except ValueError:
                pass  # Skip range check if values aren't valid numbers

        return street

    return None


def fetch_address_search_with_prefix(
    stnum: str,
    stname: str,
    prefix: str,
) -> List[Dict[str, str]]:
    """
    Two-step address search for addresses with directional prefixes.

    Step 1: GET AddressSearch.asp to get list of street variations
    Step 2: POST with selected locid to get property results

    Args:
        stnum: Street number (e.g., "303")
        stname: Street name without prefix/type (e.g., "MAYNARD")
        prefix: Directional prefix (e.g., "SE")

    Returns:
        List of property match results (same format as ValidateAddress)

    Raises:
        requests.RequestException: On network error
    """
    # Step 1: Get street selection page
    url = build_address_search_url(stnum, stname)
    logger.debug(f"Fetching AddressSearch (step 1): {url}")
    html = _fetch_with_retry(url)

    # Parse available streets
    streets = parse_address_search_streets(html)
    if not streets:
        logger.warning(f"No streets found in AddressSearch for {stnum} {stname}")
        return []

    # Find matching street with our prefix
    matching_street = find_matching_street(streets, prefix, stname, stnum)
    if not matching_street:
        logger.warning(f"No street matching prefix '{prefix}' for {stnum} {stname}")
        return []

    locid = matching_street['locid']
    logger.debug(f"Found matching street with locid={locid}: {matching_street}")

    # Step 2: POST to get property results
    # The form uses JavaScript to set locidList, then submits
    form_data = {
        'stype': 'addr',
        'stnum': stnum,
        'stname': stname.lower(),
        'locidList': locid,  # Selected street locid(s)
    }

    logger.debug(f"POSTing to AddressSearch (step 2) with locid={locid}")
    response = requests.post(
        ADDRESS_SEARCH_POST_URL,
        data=form_data,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    # Parse results (same format as ValidateAddress)
    return parse_validate_address_html(response.text)
