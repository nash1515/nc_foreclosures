"""Configuration for PropWire enrichment."""

# PropWire URLs
BASE_URL = 'https://propwire.com'
API_URL = 'https://api.propwire.com/api/auto_complete'
PROPERTY_URL_TEMPLATE = 'https://propwire.com/realestate/{address_slug}/{property_id}/property-details'

# Playwright settings
HEADLESS = True
TIMEOUT_MS = 30000  # 30 seconds for page loads
