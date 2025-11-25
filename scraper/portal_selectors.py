"""NC Courts Portal HTML selectors and constants."""

# Portal URL
PORTAL_URL = 'https://portal-nc.tylertech.cloud/Portal/Home/Dashboard/29'

# reCAPTCHA
RECAPTCHA_SITE_KEY = '6LfqmHkUAAAAAAKhHRHuxUy6LOMRZSG2LvSwWPO9'
RECAPTCHA_ELEMENT = '.g-recaptcha'
RECAPTCHA_RESPONSE_FIELD = '#g-recaptcha-response'

# Advanced Filter
ADVANCED_FILTER_LINK = 'a:has-text("Advanced")'

# Form Fields
SEARCH_CRITERIA_INPUT = '#caseCriteria_SearchCriteria'
FILE_DATE_START = '#caseCriteria\\.FileDateStart'
FILE_DATE_END = '#caseCriteria\\.FileDateEnd'
CASE_STATUS_DROPDOWN = '#caseCriteria_CaseStatus'
COURT_LOCATION_DROPDOWN = '#caseCriteria_CourtLocation'

# Submit Button
SUBMIT_BUTTON = 'input[type="submit"][name="caseCriteria.SearchCases"]'

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
