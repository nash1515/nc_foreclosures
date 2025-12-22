"""Configuration for Lee County Real Estate enrichment."""

# Lee County code (suffix of case numbers like 25SP000123-520)
COUNTY_CODE = '520'

# Lee County Tax Administration portal URLs
BASE_URL = 'https://taxaccess.leecountync.gov/pt/search/commonsearch.aspx?mode=realprop'
SEARCH_URL = 'https://taxaccess.leecountync.gov/pt/search/commonsearch.aspx?mode=realprop'

# Property detail URL - requires search session, captured from results
# Format: https://taxaccess.leecountync.gov/pt/Datalets/Datalet.aspx?sIndex=0&idx=N

# Form field IDs for address search
STREET_NUMBER_INPUT = 'input#inpNo'
STREET_NAME_INPUT = 'input#inpStreet'
SEARCH_BUTTON = 'input[type="submit"]'

# Playwright settings
HEADLESS = True
TIMEOUT_MS = 30000  # 30 seconds for page loads
