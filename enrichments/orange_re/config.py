"""Configuration for Orange County Real Estate enrichment."""

# Orange County code (suffix of case numbers like 25SP000123-670)
COUNTY_CODE = '670'

# Orange County Spatialest portal URLs
BASE_URL = 'https://property.spatialest.com/nc/orange/'
PROPERTY_URL_TEMPLATE = 'https://property.spatialest.com/nc/orange/#/property/{parcel_id}'

# Playwright settings
HEADLESS = True
TIMEOUT_MS = 30000  # 30 seconds for page loads
