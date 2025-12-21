"""Address parsing utilities for enrichment lookups."""

import re
from typing import Optional


# Street type suffixes to strip (case-insensitive)
STREET_TYPES = [
    # Full names
    'Street', 'Road', 'Drive', 'Lane', 'Avenue', 'Boulevard', 'Court',
    'Circle', 'Way', 'Place', 'Terrace', 'Trail', 'Parkway', 'Highway',
    # Abbreviations
    'St', 'Rd', 'Dr', 'Ln', 'Ave', 'Blvd', 'Ct', 'Cir', 'Wy', 'Pl',
    'Ter', 'Trl', 'Pkwy', 'Hwy',
    # With periods
    'St.', 'Rd.', 'Dr.', 'Ln.', 'Ave.', 'Blvd.', 'Ct.', 'Cir.', 'Wy.',
    'Pl.', 'Ter.', 'Trl.', 'Pkwy.', 'Hwy.',
]

# Directional prefixes
DIRECTION_PREFIXES = {
    'N': 'N', 'N.': 'N', 'North': 'N',
    'S': 'S', 'S.': 'S', 'South': 'S',
    'E': 'E', 'E.': 'E', 'East': 'E',
    'W': 'W', 'W.': 'W', 'West': 'W',
}


def normalize_street_name(name: str) -> str:
    """
    Normalize street name by removing type suffix and uppercasing.

    Args:
        name: Street name like "Salem Street" or "Main Rd."

    Returns:
        Normalized name like "SALEM" or "MAIN"
    """
    name = name.strip()

    # Sort by length descending to match longer suffixes first
    sorted_types = sorted(STREET_TYPES, key=len, reverse=True)

    for street_type in sorted_types:
        # Case-insensitive match at end of string
        pattern = re.compile(r'\s+' + re.escape(street_type) + r'$', re.IGNORECASE)
        name = pattern.sub('', name)

    return name.strip().upper()


def extract_prefix(street_part: str) -> Optional[str]:
    """
    Extract directional prefix (N/S/E/W) from street name.

    Args:
        street_part: Street name portion like "S. Salem" or "North Hills"

    Returns:
        Normalized prefix ('N', 'S', 'E', 'W') or None
    """
    parts = street_part.strip().split()
    if not parts:
        return None

    first_word = parts[0]
    return DIRECTION_PREFIXES.get(first_word)


def parse_address(address: str) -> dict:
    """
    Parse property address into components for Wake County RE lookup.

    Args:
        address: Full address like "414 S. Salem Street, Apex, NC 27502"

    Returns:
        {
            'stnum': '414',
            'prefix': 'S' or None,
            'name': 'SALEM',
            'city': 'Apex',
            'state': 'NC',
            'zipcode': '27502',
            'raw': original address
        }
    """
    result = {
        'stnum': None,
        'prefix': None,
        'name': None,
        'city': None,
        'state': None,
        'zipcode': None,
        'raw': address,
    }

    if not address:
        return result

    # Split on comma to separate street from city/state/zip
    parts = [p.strip() for p in address.split(',')]

    if not parts:
        return result

    # Parse street portion (first part)
    street_part = parts[0]

    # Extract street number (leading digits)
    stnum_match = re.match(r'^(\d+)\s+(.+)$', street_part)
    if stnum_match:
        result['stnum'] = stnum_match.group(1)
        street_name_part = stnum_match.group(2)
    else:
        street_name_part = street_part

    # Extract directional prefix
    result['prefix'] = extract_prefix(street_name_part)

    # Remove prefix from street name if present
    if result['prefix']:
        # Remove the first word (the prefix)
        name_parts = street_name_part.split()
        street_name_part = ' '.join(name_parts[1:])

    # Normalize street name (remove suffix, uppercase)
    result['name'] = normalize_street_name(street_name_part)

    # Parse city (second part)
    if len(parts) > 1:
        result['city'] = parts[1].strip()

    # Parse state and zip (third part)
    if len(parts) > 2:
        state_zip = parts[2].strip()
        state_zip_match = re.match(r'^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', state_zip)
        if state_zip_match:
            result['state'] = state_zip_match.group(1)
            result['zipcode'] = state_zip_match.group(2)
        else:
            # Try just state
            if len(state_zip) == 2 and state_zip.isalpha():
                result['state'] = state_zip.upper()

    return result
