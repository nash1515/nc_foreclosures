"""Configuration for Durham County Real Estate enrichment."""

# Durham County code (suffix of case numbers like 25SP000628-310)
COUNTY_CODE = '310'

# Durham Tax/CAMA portal URLs
BASE_URL = 'https://taxcama.dconc.gov/camapwa/'
PROPERTY_URL_TEMPLATE = 'https://taxcama.dconc.gov/camapwa/PropertySummary.aspx?PARCELPK={parcelpk}'

# Playwright settings
HEADLESS = True
TIMEOUT_MS = 30000  # 30 seconds for page loads
