"""Configuration for Chatham County Real Estate enrichment."""

# Chatham County code (suffix of case numbers like 25SP000123-180)
COUNTY_CODE = '180'

# Chatham County DEVNET wEdge portal URLs
BASE_URL = 'https://chathamnc.devnetwedge.com'
SEARCH_URL = 'https://chathamnc.devnetwedge.com/search/quick'
PROPERTY_URL_TEMPLATE = 'https://chathamnc.devnetwedge.com/parcel/view/{parcel_id}/2025'

# Request settings
TIMEOUT_SECONDS = 30
