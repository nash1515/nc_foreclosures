"""Configuration for Harnett County Real Estate enrichment."""

# Harnett County code (suffix of case numbers like 25SP000123-420)
COUNTY_CODE = '420'

# Harnett County CAMA portal URLs
BASE_URL = 'https://cama.harnett.org/ITSPublicHT/'
PROPERTY_URL_TEMPLATE = 'https://cama.harnett.org/itspublicht/AppraisalCard.aspx?prid={prid}'

# Playwright settings
HEADLESS = True
TIMEOUT_MS = 30000  # 30 seconds for page loads
