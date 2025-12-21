"""Wake County Real Estate portal configuration."""

# Base URLs
BASE_URL = "https://services.wake.gov/realestate"

PINLIST_URL_TEMPLATE = (
    f"{BASE_URL}/PinList.asp"
    "?map={map}&sheet=&block={block}&lot={lot}&spg="
)

VALIDATE_ADDRESS_URL_TEMPLATE = (
    f"{BASE_URL}/ValidateAddress.asp"
    "?stnum={stnum}&stname={stname}&locidList=&spg="
)

# AddressSearch is used for addresses with directional prefixes (N/S/E/W)
# It returns a list of streets to select from, then you POST to get results
ADDRESS_SEARCH_URL_TEMPLATE = (
    f"{BASE_URL}/AddressSearch.asp"
    "?stnum={stnum}&stname={stname}&locidList=&spg="
)

ADDRESS_SEARCH_POST_URL = f"{BASE_URL}/AddressSearch.asp"

ACCOUNT_URL_TEMPLATE = f"{BASE_URL}/Account.asp?id={{account_id}}"

# ETJ (city) code mapping - discovered dynamically, seeded with known values
ETJ_CODES = {
    'raleigh': 'RA',
    'apex': 'AP',
    'cary': 'CA',
    'fuquay-varina': 'FV',
    'fuquay varina': 'FV',
    'garner': 'GA',
    'holly springs': 'HS',
    'knightdale': 'KN',
    'morrisville': 'MO',
    'rolesville': 'RO',
    'wake forest': 'WF',
    'wendell': 'WE',
    'zebulon': 'ZE',
}

# Wake County code
COUNTY_CODE = '910'

# Parcel ID format
PARCEL_ID_LENGTH = 10
