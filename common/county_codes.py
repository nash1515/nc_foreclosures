"""North Carolina county codes mapping."""

# County name to code mapping for the 6 target counties
COUNTY_CODES = {
    'chatham': '180',
    'durham': '310',
    'harnett': '420',
    'lee': '520',
    'orange': '670',
    'wake': '910'
}

# Reverse mapping
CODE_TO_COUNTY = {v: k.title() for k, v in COUNTY_CODES.items()}


def get_county_code(county_name):
    """
    Get county code from county name.

    Args:
        county_name: County name (case insensitive)

    Returns:
        str: County code or None if not found
    """
    return COUNTY_CODES.get(county_name.lower())


def get_county_name(county_code):
    """
    Get county name from county code.

    Args:
        county_code: County code (e.g., '910')

    Returns:
        str: County name or None if not found
    """
    return CODE_TO_COUNTY.get(county_code)


def is_valid_county(county_name):
    """Check if county name is valid."""
    return county_name.lower() in COUNTY_CODES


def get_search_text(county_name, year):
    """
    Generate search text for NC Courts Portal.

    Format: YYSPnnnnnn-ccc where:
    - YY = 2-digit year
    - SP = Special Proceedings
    - nnnnnn = case number (wildcarded with *)
    - ccc = county code

    Args:
        county_name: County name
        year: 4-digit year (e.g., 2024)

    Returns:
        str: Search text (e.g., "24SP*" for Wake 2024)
    """
    year_2digit = str(year)[-2:]
    return f"{year_2digit}SP*"
