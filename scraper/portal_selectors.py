"""NC Courts Portal HTML selectors and constants."""

# Portal URL
PORTAL_URL = 'https://portal-nc.tylertech.cloud/Portal/Home/Dashboard/29'

# reCAPTCHA
RECAPTCHA_SITE_KEY = '6LfqmHkUAAAAAAKhHRHuxUy6LOMRZSG2LvSwWPO9'
RECAPTCHA_ELEMENT = '.g-recaptcha'
RECAPTCHA_RESPONSE_FIELD = '#g-recaptcha-response'

# Advanced Filter
ADVANCED_FILTER_LINK = 'a:has-text("Advanced Filtering Options")'

# Form Fields - Main search input
SEARCH_CRITERIA_INPUT = '#caseCriteria_SearchCriteria'

# Date fields (in Case Search Criteria section)
# Note: IDs have dots which need escaping in CSS, so use name selector instead
FILE_DATE_START = 'input[name="caseCriteria.FileDateStart"]'
FILE_DATE_END = 'input[name="caseCriteria.FileDateEnd"]'

# Location selection - uses CHECKBOXES not dropdown
# "All Locations" checkbox must be unchecked first, then check desired county
ALL_LOCATIONS_CHECKBOX = 'input[type="checkbox"][aria-label="All Locations"]'

# Case Type and Status - use Kendo ComboBox widgets (NOT DropDownList)
# These need JavaScript to set values
CASE_TYPE_INPUT = 'input[name="caseCriteria.CaseType"]'
CASE_STATUS_INPUT = 'input[name="caseCriteria.CaseStatus"]'

# Submit Button (there are two with same id - use first one)
SUBMIT_BUTTON = '#btnSSSubmit'

# Results Page
RESULTS_TABLE = 'table.searchResults'
RESULTS_ROWS = 'table.searchResults tbody tr'
RESULTS_COUNT_TEXT = '.pagingSummary'  # Contains "1 - 10 of 154 items"
NEXT_PAGE_BUTTON = 'a.pageLink:has-text("Next")'
ERROR_MESSAGE = '.alert-danger, .error-message'

# Case Detail Page
CASE_INFO_SECTION = '#CaseInformationContainer'
CASE_TYPE_FIELD = 'td:has-text("Case Type") + td'
CASE_STATUS_FIELD = 'td:has-text("Case Status") + td'
FILE_DATE_FIELD = 'td:has-text("File Date") + td'
EVENTS_TABLE = '#EventsTable'
EVENTS_ROWS = '#EventsTable tbody tr'
DOCUMENTS_TABLE = '#DocumentsTable'
DOCUMENTS_ROWS = '#DocumentsTable tbody tr'

# Case Type Values
SPECIAL_PROCEEDINGS = 'Special Proceedings (non-confidential)'
PENDING_STATUS = 'Pending'
