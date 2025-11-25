# NC Foreclosures - Next Steps

## Current Status

**Phase 1 Foundation:** 95% Complete ✅

### Completed
- ✅ Full infrastructure (database, VPN, CapSolver, tests)
- ✅ Portal exploration and HTML capture
- ✅ Portal selectors identified (`portal_selectors.py`)
- ✅ Portal interaction functions (`portal_interactions.py`)

### Remaining Work (5%)

#### 1. Update `scraper/initial_scrape.py`

Replace placeholder methods with actual implementations:

**In `_fill_search_form()` method** (line ~173):
```python
from scraper.portal_interactions import click_advanced_filter, fill_search_form as fill_form

def _fill_search_form(self, page):
    """Fill out the search form."""
    # Click advanced filter first
    click_advanced_filter(page)

    # Fill the form
    fill_form(
        page,
        county_name=f"{self.county.title()} County",
        start_date=self.start_date,
        end_date=self.end_date,
        search_text=get_search_text(self.county, self.start_date.year)
    )
```

**In `_solve_captcha()` method** (line ~191):
```python
from scraper.portal_interactions import solve_and_submit_captcha

def _solve_captcha(self, page):
    """Solve reCAPTCHA on the page."""
    return solve_and_submit_captcha(page)
```

**In `_check_for_too_many_results()` method** (line ~198):
```python
from scraper.portal_interactions import check_for_error

def _check_for_too_many_results(self, page):
    """Check if 'too many results' error is displayed."""
    has_error, error_msg = check_for_error(page)
    if has_error and 'too many' in error_msg.lower():
        return True
    return False
```

**In `_go_to_next_page()` method** (line ~202):
```python
from scraper.portal_interactions import go_to_next_page

def _go_to_next_page(self, page):
    """Navigate to next page of results."""
    return go_to_next_page(page)
```

#### 2. Update `scraper/page_parser.py`

Implement these functions with actual HTML parsing:

**`parse_search_results()`**:
```python
from scraper.portal_selectors import RESULTS_ROWS

def parse_search_results(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')
    cases = []

    # Find all result rows
    rows = soup.select('table.searchResults tbody tr')

    for row in rows:
        # Extract case number and URL from each row
        case_link = row.select_one('a')  # Adjust selector based on actual HTML
        if case_link:
            case_number = case_link.text.strip()
            case_url = case_link.get('href')
            # Make URL absolute if needed
            if not case_url.startswith('http'):
                case_url = f'https://portal-nc.tylertech.cloud{case_url}'

            cases.append({
                'case_number': case_number,
                'case_url': case_url
            })

    return {
        'cases': cases,
        'total_count': len(cases)
    }
```

**`parse_case_detail()`**:
```python
def parse_case_detail(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')

    case_data = {
        'case_type': None,
        'case_status': None,
        'file_date': None,
        'property_address': None,
        'events': [],
        'documents': []
    }

    # Parse case information section
    # Find the table with case details
    info_rows = soup.select('#CaseInformationContainer tr')
    for row in info_rows:
        cells = row.find_all('td')
        if len(cells) >= 2:
            label = cells[0].text.strip().lower()
            value = cells[1].text.strip()

            if 'case type' in label:
                case_data['case_type'] = value
            elif 'status' in label:
                case_data['case_status'] = value
            elif 'file date' in label:
                case_data['file_date'] = value  # Parse to date object if needed

    # Parse events table
    event_rows = soup.select('#EventsTable tbody tr')
    for row in event_rows:
        cells = row.find_all('td')
        if len(cells) >= 2:
            case_data['events'].append({
                'event_date': cells[0].text.strip(),
                'event_type': cells[1].text.strip(),
                'event_description': cells[1].text.strip()
            })

    return case_data
```

**`extract_total_count()`**:
```python
from scraper.portal_interactions import extract_total_count_from_page

def extract_total_count(page_content):
    # This can delegate to portal_interactions
    # Or parse from BeautifulSoup if needed
    soup = BeautifulSoup(page_content, 'html.parser')
    summary = soup.select_one('.pagingSummary')
    if summary:
        text = summary.text
        match = re.search(r'of\s+(\d+)\s+items', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None
```

#### 3. Test with Small Sample

Once the above is implemented:

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/phase1-foundation
source venv/bin/activate
export PYTHONPATH=$(pwd)

# Make sure VPN is ON
# Make sure PostgreSQL is running
sudo service postgresql start

# Run test scrape
PYTHONPATH=$(pwd) venv/bin/python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --test \
  --limit 5
```

#### 4. Debug and Refine

Watch the output and browser automation. Common issues:
- **Selectors not matching:** Use browser DevTools to verify selectors
- **Timing issues:** Add `time.sleep()` calls if elements load slowly
- **CAPTCHA fails:** Check CapSolver API key and balance
- **Date format:** Verify date format matches portal expectations (MM/DD/YYYY)

## Quick Commands Reference

```bash
# Activate environment
cd /home/ahn/projects/nc_foreclosures/.worktrees/phase1-foundation
source venv/bin/activate
export PYTHONPATH=$(pwd)

# Start PostgreSQL
sudo service postgresql start

# Run tests
venv/bin/python tests/test_phase1_integration.py

# Check database
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "SELECT case_number, county_name FROM cases;"

# View scrape logs
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "SELECT * FROM scrape_logs ORDER BY started_at DESC LIMIT 5;"
```

## Files to Modify

1. `scraper/initial_scrape.py` - Replace 4 placeholder methods
2. `scraper/page_parser.py` - Implement 3 parsing functions

Total: ~200-300 lines of code to complete the scraper!

## After Portal Implementation Works

1. Commit and push to GitHub
2. Test with larger samples (full month, multiple counties)
3. Merge `feature/phase1-foundation` to `main`
4. Begin Phase 2: PDF downloading and OCR
