# Wake County Real Estate Enrichment - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Wake County Real Estate enrichment module that converts parcel IDs or addresses into static property record URLs for the nc_foreclosures dashboard.

**Architecture:** Python module within nc_foreclosures that fetches Wake County RE account URLs via parcel ID (preferred) or address search (fallback). Results stored in new `enrichments` table. Triggered async on upset_bid promotion and on-demand via API.

**Tech Stack:** Python 3, SQLAlchemy, requests, BeautifulSoup, PostgreSQL, Flask API

---

## Task 1: Database Migrations

**Files:**
- Create: `database/migrations/add_parcel_id_column.sql`
- Create: `database/migrations/create_enrichments_table.sql`
- Create: `database/migrations/create_enrichment_review_log.sql`

**Step 1: Create parcel_id migration**

```sql
-- database/migrations/add_parcel_id_column.sql
-- Add parcel_id column to cases table for Wake County RE enrichment

ALTER TABLE cases ADD COLUMN IF NOT EXISTS parcel_id VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_cases_parcel_id ON cases(parcel_id);

COMMENT ON COLUMN cases.parcel_id IS 'County parcel/PIN number (10-digit for Wake County)';
```

**Step 2: Create enrichments table migration**

```sql
-- database/migrations/create_enrichments_table.sql
-- Create enrichments table for storing external property data URLs

CREATE TABLE IF NOT EXISTS enrichments (
    id SERIAL PRIMARY KEY,
    case_id INTEGER UNIQUE REFERENCES cases(id) ON DELETE CASCADE,

    -- Wake County RE enrichment
    wake_re_account VARCHAR(20),
    wake_re_url TEXT,
    wake_re_enriched_at TIMESTAMP,
    wake_re_error TEXT,

    -- Future enrichments (placeholders)
    propwire_url TEXT,
    propwire_enriched_at TIMESTAMP,
    propwire_error TEXT,

    deed_url TEXT,
    deed_enriched_at TIMESTAMP,
    deed_error TEXT,

    property_info_url TEXT,
    property_info_enriched_at TIMESTAMP,
    property_info_error TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichments_case_id ON enrichments(case_id);
CREATE INDEX IF NOT EXISTS idx_enrichments_wake_re_pending ON enrichments(case_id)
    WHERE wake_re_url IS NULL AND wake_re_error IS NULL;
```

**Step 3: Create enrichment review log migration**

```sql
-- database/migrations/create_enrichment_review_log.sql
-- Create table for logging ambiguous enrichment results requiring manual review

CREATE TABLE IF NOT EXISTS enrichment_review_log (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    enrichment_type VARCHAR(50) NOT NULL,
    search_method VARCHAR(20) NOT NULL,
    search_value TEXT NOT NULL,
    matches_found INTEGER NOT NULL,
    raw_results JSONB,
    resolution_notes TEXT,
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_review_case_id ON enrichment_review_log(case_id);
CREATE INDEX IF NOT EXISTS idx_enrichment_review_unresolved ON enrichment_review_log(resolved_at)
    WHERE resolved_at IS NULL;
```

**Step 4: Run migrations**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f database/migrations/add_parcel_id_column.sql
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f database/migrations/create_enrichments_table.sql
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f database/migrations/create_enrichment_review_log.sql
```

Expected: Each returns without errors.

**Step 5: Verify tables exist**

Run:
```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d enrichments"
```

Expected: Shows enrichments table structure with all columns.

**Step 6: Commit**

```bash
git add database/migrations/add_parcel_id_column.sql database/migrations/create_enrichments_table.sql database/migrations/create_enrichment_review_log.sql
git commit -m "feat: add database migrations for enrichments module"
```

---

## Task 2: SQLAlchemy Models

**Files:**
- Create: `enrichments/__init__.py`
- Create: `enrichments/common/__init__.py`
- Create: `enrichments/common/models.py`
- Modify: `database/models.py` (add parcel_id to Case, add relationship)

**Step 1: Create enrichments package structure**

```python
# enrichments/__init__.py
"""
Enrichments module for fetching external property data URLs.

Submodules:
- common: Shared utilities and base classes
- wake_re: Wake County Real Estate enrichment
"""
```

```python
# enrichments/common/__init__.py
"""Common enrichment utilities and base classes."""

from enrichments.common.models import Enrichment, EnrichmentReviewLog

__all__ = ['Enrichment', 'EnrichmentReviewLog']
```

**Step 2: Create SQLAlchemy models**

```python
# enrichments/common/models.py
"""SQLAlchemy models for enrichment data."""

from datetime import datetime
from database.db import db


class Enrichment(db.Model):
    """Stores enrichment URLs and metadata for cases."""

    __tablename__ = 'enrichments'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id', ondelete='CASCADE'), unique=True, nullable=False)

    # Wake County RE
    wake_re_account = db.Column(db.String(20))
    wake_re_url = db.Column(db.Text)
    wake_re_enriched_at = db.Column(db.DateTime)
    wake_re_error = db.Column(db.Text)

    # Future enrichments
    propwire_url = db.Column(db.Text)
    propwire_enriched_at = db.Column(db.DateTime)
    propwire_error = db.Column(db.Text)

    deed_url = db.Column(db.Text)
    deed_enriched_at = db.Column(db.DateTime)
    deed_error = db.Column(db.Text)

    property_info_url = db.Column(db.Text)
    property_info_enriched_at = db.Column(db.DateTime)
    property_info_error = db.Column(db.Text)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationship
    case = db.relationship('Case', backref=db.backref('enrichment', uselist=False))

    def __repr__(self):
        return f"<Enrichment case_id={self.case_id} wake_re={bool(self.wake_re_url)}>"


class EnrichmentReviewLog(db.Model):
    """Logs enrichment attempts requiring manual review (0 or 2+ matches)."""

    __tablename__ = 'enrichment_review_log'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    enrichment_type = db.Column(db.String(50), nullable=False)
    search_method = db.Column(db.String(20), nullable=False)
    search_value = db.Column(db.Text, nullable=False)
    matches_found = db.Column(db.Integer, nullable=False)
    raw_results = db.Column(db.JSON)
    resolution_notes = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Relationships
    case = db.relationship('Case', backref=db.backref('enrichment_reviews', lazy='dynamic'))
    resolver = db.relationship('User', foreign_keys=[resolved_by])

    def __repr__(self):
        status = 'resolved' if self.resolved_at else 'pending'
        return f"<EnrichmentReviewLog id={self.id} type={self.enrichment_type} status={status}>"
```

**Step 3: Add parcel_id to Case model**

Modify `database/models.py`. Find the Case class and add:

```python
# Add after other columns in Case class (around line 50-60)
parcel_id = db.Column(db.String(20))
```

**Step 4: Verify models load correctly**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from enrichments.common.models import Enrichment, EnrichmentReviewLog; print('Models loaded successfully')"
```

Expected: `Models loaded successfully`

**Step 5: Commit**

```bash
git add enrichments/__init__.py enrichments/common/__init__.py enrichments/common/models.py database/models.py
git commit -m "feat: add SQLAlchemy models for enrichments"
```

---

## Task 3: Address Parser

**Files:**
- Create: `enrichments/common/address_parser.py`
- Create: `tests/enrichments/__init__.py`
- Create: `tests/enrichments/test_address_parser.py`

**Step 1: Write the failing test**

```python
# tests/enrichments/__init__.py
"""Tests for enrichments module."""
```

```python
# tests/enrichments/test_address_parser.py
"""Tests for address parsing utilities."""

import pytest
from enrichments.common.address_parser import parse_address, normalize_street_name, extract_prefix


class TestParseAddress:
    """Tests for parse_address function."""

    def test_full_address_with_prefix(self):
        result = parse_address("414 S. Salem Street, Apex, NC 27502")
        assert result['stnum'] == '414'
        assert result['prefix'] == 'S'
        assert result['name'] == 'SALEM'
        assert result['city'] == 'Apex'

    def test_address_without_prefix(self):
        result = parse_address("123 Main Street, Raleigh, NC 27601")
        assert result['stnum'] == '123'
        assert result['prefix'] is None
        assert result['name'] == 'MAIN'
        assert result['city'] == 'Raleigh'

    def test_address_with_north_prefix(self):
        result = parse_address("500 North Hills Drive, Raleigh, NC 27609")
        assert result['stnum'] == '500'
        assert result['prefix'] == 'N'
        assert result['name'] == 'HILLS'

    def test_address_multi_word_street(self):
        result = parse_address("513 Sweet Laurel Lane, Apex, NC 27523")
        assert result['stnum'] == '513'
        assert result['name'] == 'SWEET LAUREL'


class TestNormalizeStreetName:
    """Tests for normalize_street_name function."""

    def test_strips_street_suffix(self):
        assert normalize_street_name("Salem Street") == "SALEM"

    def test_strips_road_suffix(self):
        assert normalize_street_name("Main Rd.") == "MAIN"

    def test_strips_drive_suffix(self):
        assert normalize_street_name("Oak Dr") == "OAK"

    def test_strips_lane_suffix(self):
        assert normalize_street_name("Sweet Laurel Lane") == "SWEET LAUREL"

    def test_strips_boulevard(self):
        assert normalize_street_name("Capital Blvd") == "CAPITAL"

    def test_handles_court(self):
        assert normalize_street_name("Kings Ct.") == "KINGS"


class TestExtractPrefix:
    """Tests for extract_prefix function."""

    def test_extracts_south(self):
        assert extract_prefix("S. Salem") == "S"

    def test_extracts_north(self):
        assert extract_prefix("North Hills") == "N"

    def test_extracts_east(self):
        assert extract_prefix("E Main") == "E"

    def test_extracts_west(self):
        assert extract_prefix("West Oak") == "W"

    def test_no_prefix(self):
        assert extract_prefix("Main") is None

    def test_no_prefix_regular_word(self):
        assert extract_prefix("Sweet Laurel") is None
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) pytest tests/enrichments/test_address_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'enrichments.common.address_parser'`

**Step 3: Write the implementation**

```python
# enrichments/common/address_parser.py
"""Address parsing utilities for enrichment lookups."""

import re
from typing import Optional


# Street type suffixes to strip (case-insensitive)
STREET_TYPES = [
    # Full names
    'Street', 'Road', 'Drive', 'Lane', 'Avenue', 'Boulevard', 'Court',
    'Circle', 'Way', 'Place', 'Terrace', 'Trail', 'Parkway', 'Highway',
    # Abbreviations
    'St', 'Rd', 'Dr', 'Ln', 'Ave', 'Blvd', 'Ct', 'Cir', 'Wy', 'Pl',
    'Ter', 'Trl', 'Pkwy', 'Hwy',
    # With periods
    'St.', 'Rd.', 'Dr.', 'Ln.', 'Ave.', 'Blvd.', 'Ct.', 'Cir.', 'Wy.',
    'Pl.', 'Ter.', 'Trl.', 'Pkwy.', 'Hwy.',
]

# Directional prefixes
DIRECTION_PREFIXES = {
    'N': 'N', 'N.': 'N', 'North': 'N',
    'S': 'S', 'S.': 'S', 'South': 'S',
    'E': 'E', 'E.': 'E', 'East': 'E',
    'W': 'W', 'W.': 'W', 'West': 'W',
}


def normalize_street_name(name: str) -> str:
    """
    Normalize street name by removing type suffix and uppercasing.

    Args:
        name: Street name like "Salem Street" or "Main Rd."

    Returns:
        Normalized name like "SALEM" or "MAIN"
    """
    name = name.strip()

    # Sort by length descending to match longer suffixes first
    sorted_types = sorted(STREET_TYPES, key=len, reverse=True)

    for street_type in sorted_types:
        # Case-insensitive match at end of string
        pattern = re.compile(r'\s+' + re.escape(street_type) + r'$', re.IGNORECASE)
        name = pattern.sub('', name)

    return name.strip().upper()


def extract_prefix(street_part: str) -> Optional[str]:
    """
    Extract directional prefix (N/S/E/W) from street name.

    Args:
        street_part: Street name portion like "S. Salem" or "North Hills"

    Returns:
        Normalized prefix ('N', 'S', 'E', 'W') or None
    """
    parts = street_part.strip().split()
    if not parts:
        return None

    first_word = parts[0]
    return DIRECTION_PREFIXES.get(first_word)


def parse_address(address: str) -> dict:
    """
    Parse property address into components for Wake County RE lookup.

    Args:
        address: Full address like "414 S. Salem Street, Apex, NC 27502"

    Returns:
        {
            'stnum': '414',
            'prefix': 'S' or None,
            'name': 'SALEM',
            'city': 'Apex',
            'state': 'NC',
            'zipcode': '27502',
            'raw': original address
        }
    """
    result = {
        'stnum': None,
        'prefix': None,
        'name': None,
        'city': None,
        'state': None,
        'zipcode': None,
        'raw': address,
    }

    if not address:
        return result

    # Split on comma to separate street from city/state/zip
    parts = [p.strip() for p in address.split(',')]

    if not parts:
        return result

    # Parse street portion (first part)
    street_part = parts[0]

    # Extract street number (leading digits)
    stnum_match = re.match(r'^(\d+)\s+(.+)$', street_part)
    if stnum_match:
        result['stnum'] = stnum_match.group(1)
        street_name_part = stnum_match.group(2)
    else:
        street_name_part = street_part

    # Extract directional prefix
    result['prefix'] = extract_prefix(street_name_part)

    # Remove prefix from street name if present
    if result['prefix']:
        # Remove the first word (the prefix)
        name_parts = street_name_part.split()
        street_name_part = ' '.join(name_parts[1:])

    # Normalize street name (remove suffix, uppercase)
    result['name'] = normalize_street_name(street_name_part)

    # Parse city (second part)
    if len(parts) > 1:
        result['city'] = parts[1].strip()

    # Parse state and zip (third part)
    if len(parts) > 2:
        state_zip = parts[2].strip()
        state_zip_match = re.match(r'^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', state_zip)
        if state_zip_match:
            result['state'] = state_zip_match.group(1)
            result['zipcode'] = state_zip_match.group(2)
        else:
            # Try just state
            if len(state_zip) == 2 and state_zip.isalpha():
                result['state'] = state_zip.upper()

    return result
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) pytest tests/enrichments/test_address_parser.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add enrichments/common/address_parser.py tests/enrichments/__init__.py tests/enrichments/test_address_parser.py
git commit -m "feat: add address parser for Wake County RE enrichment"
```

---

## Task 4: Wake RE URL Builder

**Files:**
- Create: `enrichments/wake_re/__init__.py`
- Create: `enrichments/wake_re/config.py`
- Create: `enrichments/wake_re/url_builder.py`
- Create: `tests/enrichments/test_url_builder.py`

**Step 1: Write the failing test**

```python
# tests/enrichments/test_url_builder.py
"""Tests for Wake County RE URL builder."""

import pytest
from enrichments.wake_re.url_builder import (
    parse_parcel_id,
    build_pinlist_url,
    build_validate_address_url,
    build_account_url,
)


class TestParseParcelId:
    """Tests for parcel ID parsing (4-2-4 split)."""

    def test_standard_parcel_id(self):
        result = parse_parcel_id("0753018148")
        assert result == {'map': '0753', 'block': '01', 'lot': '8148'}

    def test_another_parcel_id(self):
        result = parse_parcel_id("0787005323")
        assert result == {'map': '0787', 'block': '00', 'lot': '5323'}

    def test_invalid_length_returns_none(self):
        assert parse_parcel_id("12345") is None

    def test_non_numeric_returns_none(self):
        assert parse_parcel_id("ABC1234567") is None

    def test_empty_returns_none(self):
        assert parse_parcel_id("") is None

    def test_none_returns_none(self):
        assert parse_parcel_id(None) is None


class TestBuildPinlistUrl:
    """Tests for PinList URL construction."""

    def test_builds_correct_url(self):
        url = build_pinlist_url("0753018148")
        assert "map=0753" in url
        assert "block=01" in url
        assert "lot=8148" in url
        assert "services.wake.gov/realestate/PinList.asp" in url

    def test_invalid_parcel_returns_none(self):
        assert build_pinlist_url("invalid") is None


class TestBuildValidateAddressUrl:
    """Tests for ValidateAddress URL construction."""

    def test_builds_correct_url(self):
        url = build_validate_address_url("414", "salem")
        assert "stnum=414" in url
        assert "stname=salem" in url
        assert "services.wake.gov/realestate/ValidateAddress.asp" in url

    def test_encodes_spaces(self):
        url = build_validate_address_url("513", "sweet laurel")
        assert "stname=sweet+laurel" in url


class TestBuildAccountUrl:
    """Tests for Account URL construction."""

    def test_builds_correct_url(self):
        url = build_account_url("0379481")
        assert url == "https://services.wake.gov/realestate/Account.asp?id=0379481"

    def test_another_account(self):
        url = build_account_url("0045436")
        assert url == "https://services.wake.gov/realestate/Account.asp?id=0045436"
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) pytest tests/enrichments/test_url_builder.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
# enrichments/wake_re/__init__.py
"""Wake County Real Estate enrichment module."""

from enrichments.wake_re.enricher import enrich_case

__all__ = ['enrich_case']
```

```python
# enrichments/wake_re/config.py
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
```

```python
# enrichments/wake_re/url_builder.py
"""URL construction for Wake County Real Estate portal."""

from typing import Optional
from urllib.parse import quote_plus

from enrichments.wake_re.config import (
    PINLIST_URL_TEMPLATE,
    VALIDATE_ADDRESS_URL_TEMPLATE,
    ACCOUNT_URL_TEMPLATE,
    PARCEL_ID_LENGTH,
)


def parse_parcel_id(parcel_id: str) -> Optional[dict]:
    """
    Parse 10-digit Wake County parcel ID into components.

    Format: MMMMBBLLLL (4-2-4 split)
        - MMMM: Map number (first 4 digits)
        - BB: Block number (next 2 digits)
        - LLLL: Lot number (last 4 digits)

    Args:
        parcel_id: 10-digit parcel ID like "0753018148"

    Returns:
        {'map': '0753', 'block': '01', 'lot': '8148'} or None if invalid
    """
    if not parcel_id:
        return None

    parcel_id = str(parcel_id).strip()

    if len(parcel_id) != PARCEL_ID_LENGTH:
        return None

    if not parcel_id.isdigit():
        return None

    return {
        'map': parcel_id[0:4],
        'block': parcel_id[4:6],
        'lot': parcel_id[6:10],
    }


def build_pinlist_url(parcel_id: str) -> Optional[str]:
    """
    Build PinList URL from parcel ID.

    Args:
        parcel_id: 10-digit parcel ID

    Returns:
        Full URL or None if parcel ID invalid
    """
    parsed = parse_parcel_id(parcel_id)
    if not parsed:
        return None

    return PINLIST_URL_TEMPLATE.format(**parsed)


def build_validate_address_url(stnum: str, stname: str) -> str:
    """
    Build ValidateAddress URL from address components.

    Args:
        stnum: Street number (e.g., "414")
        stname: Street name without type suffix (e.g., "salem")

    Returns:
        Full URL with URL-encoded parameters
    """
    # URL encode with + for spaces
    encoded_stname = quote_plus(stname.lower())

    return VALIDATE_ADDRESS_URL_TEMPLATE.format(
        stnum=stnum,
        stname=encoded_stname,
    )


def build_account_url(account_id: str) -> str:
    """
    Build final Account.asp URL.

    Args:
        account_id: Wake County account ID (e.g., "0379481")

    Returns:
        Full URL to property account page
    """
    return ACCOUNT_URL_TEMPLATE.format(account_id=account_id)
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) pytest tests/enrichments/test_url_builder.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add enrichments/wake_re/__init__.py enrichments/wake_re/config.py enrichments/wake_re/url_builder.py tests/enrichments/test_url_builder.py
git commit -m "feat: add Wake RE URL builder with parcel ID parsing"
```

---

## Task 5: Wake RE Scraper

**Files:**
- Create: `enrichments/wake_re/scraper.py`
- Create: `tests/enrichments/test_scraper.py`

**Step 1: Write the failing test**

```python
# tests/enrichments/test_scraper.py
"""Tests for Wake County RE page scraper."""

import pytest
from enrichments.wake_re.scraper import (
    parse_pinlist_html,
    parse_validate_address_html,
    match_address_result,
)


class TestParsePinlistHtml:
    """Tests for PinList page parsing."""

    def test_extracts_single_account(self):
        html = """
        <html>
        <body>
        <table>
            <tr>
                <td>1</td>
                <td><a href="Account.asp?id=0379481">0379481</a></td>
                <td>414</td>
                <td>S</td>
                <td>SALEM</td>
                <td>ST</td>
            </tr>
        </table>
        </body>
        </html>
        """
        results = parse_pinlist_html(html)
        assert len(results) == 1
        assert results[0]['account_id'] == '0379481'

    def test_extracts_multiple_accounts(self):
        html = """
        <html>
        <body>
        <table>
            <tr>
                <td><a href="Account.asp?id=0379481">0379481</a></td>
            </tr>
            <tr>
                <td><a href="Account.asp?id=0379482">0379482</a></td>
            </tr>
        </table>
        </body>
        </html>
        """
        results = parse_pinlist_html(html)
        assert len(results) == 2

    def test_no_results_returns_empty(self):
        html = "<html><body><p>No records found</p></body></html>"
        results = parse_pinlist_html(html)
        assert len(results) == 0


class TestParseValidateAddressHtml:
    """Tests for ValidateAddress page parsing."""

    def test_extracts_address_results(self):
        html = """
        <html>
        <body>
        <table>
            <tr>
                <td>1</td>
                <td><a href="Account.asp?id=0045436">0045436</a></td>
                <td>414</td>
                <td></td>
                <td>S</td>
                <td>SALEM</td>
                <td>ST</td>
                <td></td>
                <td>AP</td>
                <td>ATM DEVELOPMENT LLC</td>
            </tr>
        </table>
        </body>
        </html>
        """
        results = parse_validate_address_html(html)
        assert len(results) == 1
        assert results[0]['account_id'] == '0045436'
        assert results[0]['stnum'] == '414'
        assert results[0]['prefix'] == 'S'
        assert results[0]['street_name'] == 'SALEM'
        assert results[0]['etj'] == 'AP'


class TestMatchAddressResult:
    """Tests for address result matching."""

    def test_matches_exact(self):
        results = [
            {'account_id': '001', 'stnum': '414', 'prefix': 'S', 'street_name': 'SALEM', 'etj': 'AP'},
            {'account_id': '002', 'stnum': '414', 'prefix': 'N', 'street_name': 'SALEM', 'etj': 'AP'},
        ]
        match = match_address_result(results, stnum='414', prefix='S', name='SALEM', etj='AP')
        assert match is not None
        assert match['account_id'] == '001'

    def test_no_match_returns_none(self):
        results = [
            {'account_id': '001', 'stnum': '414', 'prefix': 'S', 'street_name': 'SALEM', 'etj': 'AP'},
        ]
        match = match_address_result(results, stnum='500', prefix='S', name='SALEM', etj='AP')
        assert match is None

    def test_matches_without_prefix(self):
        results = [
            {'account_id': '001', 'stnum': '123', 'prefix': '', 'street_name': 'MAIN', 'etj': 'RA'},
        ]
        match = match_address_result(results, stnum='123', prefix=None, name='MAIN', etj='RA')
        assert match is not None
        assert match['account_id'] == '001'
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) pytest tests/enrichments/test_scraper.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write the implementation**

```python
# enrichments/wake_re/scraper.py
"""Page scraping for Wake County Real Estate portal."""

import re
import logging
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from enrichments.wake_re.url_builder import (
    build_pinlist_url,
    build_validate_address_url,
)


logger = logging.getLogger(__name__)

# Request settings
REQUEST_TIMEOUT = 30
MAX_RETRIES = 1
RETRY_DELAY = 2


def _fetch_with_retry(url: str) -> str:
    """
    Fetch URL with retry logic.

    Args:
        url: URL to fetch

    Returns:
        HTML content

    Raises:
        requests.RequestException: If all retries fail
    """
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            last_error = e
            if attempt < MAX_RETRIES:
                logger.warning(f"Fetch attempt {attempt + 1} failed: {e}")
                time.sleep(RETRY_DELAY * (attempt + 1))

    raise last_error


def parse_pinlist_html(html: str) -> List[Dict[str, str]]:
    """
    Parse PinList results page.

    Args:
        html: Raw HTML from PinList.asp

    Returns:
        List of dicts with account_id and other fields
    """
    results = []
    soup = BeautifulSoup(html, 'html.parser')

    # Find all account links
    account_pattern = re.compile(r'Account\.asp\?id=(\d+)')

    for link in soup.find_all('a', href=account_pattern):
        match = account_pattern.search(link.get('href', ''))
        if match:
            results.append({
                'account_id': match.group(1),
                'link_text': link.get_text(strip=True),
            })

    return results


def parse_validate_address_html(html: str) -> List[Dict[str, str]]:
    """
    Parse ValidateAddress results page.

    Expects table with columns:
    Line | Account | St Num | St Misc | Pfx | Street Name | Type | Sfx | ETJ | Owner

    Args:
        html: Raw HTML from ValidateAddress.asp

    Returns:
        List of dicts with parsed row data
    """
    results = []
    soup = BeautifulSoup(html, 'html.parser')

    # Find account links and their parent rows
    account_pattern = re.compile(r'Account\.asp\?id=(\d+)')

    for link in soup.find_all('a', href=account_pattern):
        match = account_pattern.search(link.get('href', ''))
        if not match:
            continue

        account_id = match.group(1)

        # Find parent row
        row = link.find_parent('tr')
        if not row:
            continue

        cells = row.find_all('td')
        if len(cells) < 9:
            continue

        # Parse based on expected column order
        # Line(0) | Account(1) | St Num(2) | St Misc(3) | Pfx(4) | Street Name(5) | Type(6) | Sfx(7) | ETJ(8) | Owner(9)
        try:
            result = {
                'account_id': account_id,
                'stnum': cells[2].get_text(strip=True),
                'st_misc': cells[3].get_text(strip=True),
                'prefix': cells[4].get_text(strip=True),
                'street_name': cells[5].get_text(strip=True),
                'street_type': cells[6].get_text(strip=True),
                'suffix': cells[7].get_text(strip=True),
                'etj': cells[8].get_text(strip=True),
            }
            if len(cells) > 9:
                result['owner'] = cells[9].get_text(strip=True)
            results.append(result)
        except (IndexError, AttributeError) as e:
            logger.warning(f"Failed to parse row: {e}")
            continue

    return results


def match_address_result(
    results: List[Dict[str, str]],
    stnum: str,
    prefix: Optional[str],
    name: str,
    etj: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """
    Find single matching result from ValidateAddress output.

    Args:
        results: Parsed results from parse_validate_address_html
        stnum: Street number to match
        prefix: Directional prefix (N/S/E/W) or None
        name: Street name (uppercase)
        etj: City code (optional)

    Returns:
        Single matching row or None
    """
    matches = []

    for row in results:
        # Match street number
        if row.get('stnum') != stnum:
            continue

        # Match prefix (empty string or None both mean no prefix)
        row_prefix = row.get('prefix', '').strip()
        search_prefix = (prefix or '').strip()
        if row_prefix.upper() != search_prefix.upper():
            continue

        # Match street name
        if row.get('street_name', '').upper() != name.upper():
            continue

        # Match ETJ if provided
        if etj and row.get('etj', '').upper() != etj.upper():
            continue

        matches.append(row)

    # Only return if exactly one match
    if len(matches) == 1:
        return matches[0]

    return None


def fetch_pinlist_results(parcel_id: str) -> List[Dict[str, str]]:
    """
    Fetch and parse PinList results for a parcel ID.

    Args:
        parcel_id: 10-digit Wake County parcel ID

    Returns:
        List of account results

    Raises:
        requests.RequestException: On network error
    """
    url = build_pinlist_url(parcel_id)
    if not url:
        return []

    logger.debug(f"Fetching PinList: {url}")
    html = _fetch_with_retry(url)
    return parse_pinlist_html(html)


def fetch_validate_address_results(stnum: str, stname: str) -> List[Dict[str, str]]:
    """
    Fetch and parse ValidateAddress results.

    Args:
        stnum: Street number
        stname: Street name (without type suffix)

    Returns:
        List of address match results

    Raises:
        requests.RequestException: On network error
    """
    url = build_validate_address_url(stnum, stname)

    logger.debug(f"Fetching ValidateAddress: {url}")
    html = _fetch_with_retry(url)
    return parse_validate_address_html(html)
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) pytest tests/enrichments/test_scraper.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add enrichments/wake_re/scraper.py tests/enrichments/test_scraper.py
git commit -m "feat: add Wake RE page scraper with HTML parsing"
```

---

## Task 6: Base Enricher Class

**Files:**
- Create: `enrichments/common/base_enricher.py`

**Step 1: Write the base class**

```python
# enrichments/common/base_enricher.py
"""Abstract base class for enrichment modules."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from database.db import db
from enrichments.common.models import Enrichment, EnrichmentReviewLog


logger = logging.getLogger(__name__)


class EnrichmentResult:
    """Result object for enrichment operations."""

    def __init__(
        self,
        success: bool,
        url: Optional[str] = None,
        account_id: Optional[str] = None,
        error: Optional[str] = None,
        review_needed: bool = False,
    ):
        self.success = success
        self.url = url
        self.account_id = account_id
        self.error = error
        self.review_needed = review_needed

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'url': self.url,
            'account_id': self.account_id,
            'error': self.error,
            'review_needed': self.review_needed,
        }


class BaseEnricher(ABC):
    """Abstract base class for all enrichment modules."""

    # Subclasses must define these
    enrichment_type: str = None  # e.g., 'wake_re', 'durham_re'

    @abstractmethod
    def enrich(self, case_id: int) -> EnrichmentResult:
        """
        Enrich a case with external data.

        Args:
            case_id: Database ID of the case to enrich

        Returns:
            EnrichmentResult with success status and data
        """
        pass

    def _get_or_create_enrichment(self, case_id: int) -> Enrichment:
        """Get existing enrichment record or create new one."""
        enrichment = db.session.query(Enrichment).filter_by(case_id=case_id).first()
        if not enrichment:
            enrichment = Enrichment(case_id=case_id)
            db.session.add(enrichment)
        return enrichment

    def _log_review(
        self,
        case_id: int,
        search_method: str,
        search_value: str,
        matches_found: int,
        raw_results: dict,
    ) -> EnrichmentReviewLog:
        """
        Log cases needing manual review to enrichment_review_log.

        Args:
            case_id: Case database ID
            search_method: 'parcel_id' or 'address'
            search_value: The value used for search
            matches_found: Number of matches (0 or 2+)
            raw_results: Raw search results for debugging

        Returns:
            Created review log entry
        """
        log = EnrichmentReviewLog(
            case_id=case_id,
            enrichment_type=self.enrichment_type,
            search_method=search_method,
            search_value=search_value,
            matches_found=matches_found,
            raw_results=raw_results,
        )
        db.session.add(log)
        db.session.commit()

        logger.warning(
            f"Case {case_id}: {matches_found} matches for {search_method}='{search_value}' - logged for review"
        )

        return log

    def _save_success(
        self,
        case_id: int,
        url: str,
        account_id: str,
    ) -> None:
        """Save successful enrichment result."""
        enrichment = self._get_or_create_enrichment(case_id)

        # Set type-specific fields (subclass should override for specific fields)
        self._set_enrichment_fields(enrichment, url, account_id, error=None)

        db.session.commit()
        logger.info(f"Case {case_id}: {self.enrichment_type} enrichment succeeded - {url}")

    def _save_error(
        self,
        case_id: int,
        error: str,
    ) -> None:
        """Save enrichment error."""
        enrichment = self._get_or_create_enrichment(case_id)

        self._set_enrichment_fields(enrichment, url=None, account_id=None, error=error)

        db.session.commit()
        logger.error(f"Case {case_id}: {self.enrichment_type} enrichment failed - {error}")

    @abstractmethod
    def _set_enrichment_fields(
        self,
        enrichment: Enrichment,
        url: Optional[str],
        account_id: Optional[str],
        error: Optional[str],
    ) -> None:
        """
        Set enrichment-type-specific fields on the enrichment record.

        Subclasses must implement to set their specific columns.
        """
        pass
```

**Step 2: Verify it loads**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult; print('Base enricher loaded')"
```

Expected: `Base enricher loaded`

**Step 3: Commit**

```bash
git add enrichments/common/base_enricher.py
git commit -m "feat: add abstract base enricher class"
```

---

## Task 7: Wake RE Enricher (Main Entry Point)

**Files:**
- Create: `enrichments/wake_re/enricher.py`
- Create: `tests/enrichments/test_wake_re_enricher.py`

**Step 1: Write the failing test**

```python
# tests/enrichments/test_wake_re_enricher.py
"""Tests for Wake County RE enricher."""

import pytest
from unittest import mock

from enrichments.wake_re.enricher import WakeREEnricher, enrich_case
from enrichments.common.base_enricher import EnrichmentResult


class TestWakeREEnricher:
    """Tests for WakeREEnricher class."""

    @mock.patch('enrichments.wake_re.enricher.fetch_pinlist_results')
    def test_enrich_with_parcel_id_success(self, mock_fetch, test_app, test_case_with_parcel):
        """Test successful enrichment via parcel ID."""
        mock_fetch.return_value = [{'account_id': '0379481'}]

        enricher = WakeREEnricher()
        result = enricher.enrich(test_case_with_parcel.id)

        assert result.success is True
        assert result.account_id == '0379481'
        assert 'Account.asp?id=0379481' in result.url

    @mock.patch('enrichments.wake_re.enricher.fetch_validate_address_results')
    @mock.patch('enrichments.wake_re.enricher.match_address_result')
    def test_enrich_with_address_fallback(self, mock_match, mock_fetch, test_app, test_case_with_address):
        """Test enrichment falls back to address when no parcel ID."""
        mock_fetch.return_value = [{'account_id': '0045436', 'stnum': '414', 'prefix': 'S', 'street_name': 'SALEM', 'etj': 'AP'}]
        mock_match.return_value = {'account_id': '0045436'}

        enricher = WakeREEnricher()
        result = enricher.enrich(test_case_with_address.id)

        assert result.success is True
        assert result.account_id == '0045436'

    @mock.patch('enrichments.wake_re.enricher.fetch_pinlist_results')
    def test_enrich_no_matches_logs_review(self, mock_fetch, test_app, test_case_with_parcel):
        """Test that zero matches logs to review queue."""
        mock_fetch.return_value = []

        enricher = WakeREEnricher()
        result = enricher.enrich(test_case_with_parcel.id)

        assert result.success is False
        assert result.review_needed is True


# Fixtures would be in conftest.py
@pytest.fixture
def test_app():
    """Create test Flask app context."""
    from web_app.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        yield app


@pytest.fixture
def test_case_with_parcel(test_app):
    """Create test case with parcel ID."""
    from database.models import Case
    from database.db import db

    case = Case(
        case_number='TEST-PARCEL-001',
        county_code='910',
        parcel_id='0753018148',
    )
    db.session.add(case)
    db.session.commit()
    yield case
    db.session.delete(case)
    db.session.commit()


@pytest.fixture
def test_case_with_address(test_app):
    """Create test case with address only."""
    from database.models import Case
    from database.db import db

    case = Case(
        case_number='TEST-ADDR-001',
        county_code='910',
        property_address='414 S. Salem Street, Apex, NC 27502',
    )
    db.session.add(case)
    db.session.commit()
    yield case
    db.session.delete(case)
    db.session.commit()
```

**Step 2: Write the implementation**

```python
# enrichments/wake_re/enricher.py
"""Main enricher for Wake County Real Estate."""

import logging
from datetime import datetime
from typing import Optional

from database.db import db
from database.models import Case
from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult
from enrichments.common.models import Enrichment
from enrichments.common.address_parser import parse_address
from enrichments.wake_re.config import ETJ_CODES, COUNTY_CODE
from enrichments.wake_re.url_builder import build_account_url, parse_parcel_id
from enrichments.wake_re.scraper import (
    fetch_pinlist_results,
    fetch_validate_address_results,
    match_address_result,
)


logger = logging.getLogger(__name__)


class WakeREEnricher(BaseEnricher):
    """Enricher for Wake County Real Estate URLs."""

    enrichment_type = 'wake_re'

    def enrich(self, case_id: int) -> EnrichmentResult:
        """
        Enrich a case with Wake County RE URL.

        Strategy:
            1. Try parcel ID lookup if available
            2. Fall back to address search
            3. Log ambiguous cases for review

        Args:
            case_id: Database ID of the case

        Returns:
            EnrichmentResult with success status and URL
        """
        # Fetch case
        case = db.session.query(Case).get(case_id)
        if not case:
            return EnrichmentResult(success=False, error=f"Case {case_id} not found")

        if case.county_code != COUNTY_CODE:
            return EnrichmentResult(
                success=False,
                error=f"Case {case.case_number} is not Wake County (code={case.county_code})"
            )

        logger.info(f"Enriching case {case.case_number} with Wake RE data")

        # Try parcel ID first
        if case.parcel_id and parse_parcel_id(case.parcel_id):
            result = self._enrich_by_parcel_id(case)
            if result.success or result.review_needed:
                return result
            # If parcel ID failed (not review), fall through to address
            logger.info(f"Parcel ID lookup failed for {case.case_number}, trying address")

        # Fall back to address
        if case.property_address:
            return self._enrich_by_address(case)

        # No parcel ID or address
        error = "No parcel_id or property_address available"
        self._save_error(case_id, error)
        return EnrichmentResult(success=False, error=error)

    def _enrich_by_parcel_id(self, case: Case) -> EnrichmentResult:
        """Enrich using parcel ID lookup."""
        try:
            results = fetch_pinlist_results(case.parcel_id)
        except Exception as e:
            error = f"PinList fetch error: {e}"
            self._save_error(case.id, error)
            return EnrichmentResult(success=False, error=error)

        if len(results) == 1:
            # Success - single match
            account_id = results[0]['account_id']
            url = build_account_url(account_id)
            self._save_success(case.id, url, account_id)
            return EnrichmentResult(success=True, url=url, account_id=account_id)

        elif len(results) == 0:
            # No matches - log for review
            self._log_review(
                case_id=case.id,
                search_method='parcel_id',
                search_value=case.parcel_id,
                matches_found=0,
                raw_results={'results': results},
            )
            return EnrichmentResult(success=False, review_needed=True, error="No matches found")

        else:
            # Multiple matches - log for review
            self._log_review(
                case_id=case.id,
                search_method='parcel_id',
                search_value=case.parcel_id,
                matches_found=len(results),
                raw_results={'results': results},
            )
            return EnrichmentResult(success=False, review_needed=True, error=f"{len(results)} matches found")

    def _enrich_by_address(self, case: Case) -> EnrichmentResult:
        """Enrich using address search."""
        # Parse address
        parsed = parse_address(case.property_address)

        if not parsed.get('stnum') or not parsed.get('name'):
            error = f"Could not parse address: {case.property_address}"
            self._save_error(case.id, error)
            return EnrichmentResult(success=False, error=error)

        # Fetch address search results
        try:
            results = fetch_validate_address_results(parsed['stnum'], parsed['name'])
        except Exception as e:
            error = f"Address search error: {e}"
            self._save_error(case.id, error)
            return EnrichmentResult(success=False, error=error)

        # Get ETJ code for city matching
        etj = None
        if parsed.get('city'):
            etj = ETJ_CODES.get(parsed['city'].lower())

        # Try to find single match
        match = match_address_result(
            results,
            stnum=parsed['stnum'],
            prefix=parsed['prefix'],
            name=parsed['name'],
            etj=etj,
        )

        if match:
            account_id = match['account_id']
            url = build_account_url(account_id)
            self._save_success(case.id, url, account_id)
            return EnrichmentResult(success=True, url=url, account_id=account_id)

        # No single match - determine reason and log
        matches_count = len(results) if results else 0
        self._log_review(
            case_id=case.id,
            search_method='address',
            search_value=case.property_address,
            matches_found=matches_count,
            raw_results={'parsed': parsed, 'results': results},
        )
        return EnrichmentResult(
            success=False,
            review_needed=True,
            error=f"{matches_count} matches found for address"
        )

    def _set_enrichment_fields(
        self,
        enrichment: Enrichment,
        url: Optional[str],
        account_id: Optional[str],
        error: Optional[str],
    ) -> None:
        """Set Wake RE specific fields."""
        enrichment.wake_re_url = url
        enrichment.wake_re_account = account_id
        enrichment.wake_re_error = error
        enrichment.wake_re_enriched_at = datetime.now() if url else None
        enrichment.updated_at = datetime.now()


def enrich_case(case_id: int) -> dict:
    """
    Convenience function for external calls.

    Args:
        case_id: Database ID of the case to enrich

    Returns:
        Dict with success status and enrichment data
    """
    enricher = WakeREEnricher()
    result = enricher.enrich(case_id)
    return result.to_dict()
```

**Step 3: Update wake_re __init__.py**

The `enrichments/wake_re/__init__.py` already imports `enrich_case` - verify it works:

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from enrichments.wake_re import enrich_case; print('Wake RE enricher loaded')"
```

Expected: `Wake RE enricher loaded`

**Step 4: Commit**

```bash
git add enrichments/wake_re/enricher.py tests/enrichments/test_wake_re_enricher.py
git commit -m "feat: add Wake RE enricher with parcel ID and address fallback"
```

---

## Task 8: API Endpoints

**Files:**
- Create: `web_app/api/enrichments.py`
- Modify: `web_app/app.py` (register blueprint)

**Step 1: Create enrichments API**

```python
# web_app/api/enrichments.py
"""API endpoints for enrichment operations."""

import logging
from flask import Blueprint, jsonify, request

from database.db import db
from database.models import Case
from web_app.auth.middleware import require_auth
from enrichments.common.models import Enrichment, EnrichmentReviewLog
from enrichments.wake_re import enrich_case as enrich_wake_re
from enrichments.wake_re.url_builder import build_account_url


logger = logging.getLogger(__name__)

bp = Blueprint('enrichments', __name__)


@bp.route('/api/enrichments/wake-re/<int:case_id>', methods=['POST'])
@require_auth
def trigger_wake_re_enrichment(case_id):
    """
    Manually trigger Wake RE enrichment for a case.

    Use cases:
        - Retry failed enrichments
        - Enrich historical cases
        - On-demand enrichment
    """
    try:
        result = enrich_wake_re(case_id)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.exception(f"Error enriching case {case_id}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/enrichments/review-queue', methods=['GET'])
@require_auth
def get_review_queue():
    """
    Fetch unresolved enrichment review items.

    Query params:
        - enrichment_type: Filter by type (e.g., 'wake_re')
        - limit: Max results (default 50)
    """
    enrichment_type = request.args.get('enrichment_type')
    limit = request.args.get('limit', 50, type=int)

    query = db.session.query(EnrichmentReviewLog).filter(
        EnrichmentReviewLog.resolved_at.is_(None)
    ).order_by(EnrichmentReviewLog.created_at.desc())

    if enrichment_type:
        query = query.filter(EnrichmentReviewLog.enrichment_type == enrichment_type)

    logs = query.limit(limit).all()

    results = []
    for log in logs:
        case = db.session.query(Case).get(log.case_id)
        results.append({
            'id': log.id,
            'case_id': log.case_id,
            'case_number': case.case_number if case else None,
            'enrichment_type': log.enrichment_type,
            'search_method': log.search_method,
            'search_value': log.search_value,
            'matches_found': log.matches_found,
            'raw_results': log.raw_results,
            'created_at': log.created_at.isoformat() if log.created_at else None,
        })

    return jsonify(results)


@bp.route('/api/enrichments/resolve/<int:log_id>', methods=['POST'])
@require_auth
def resolve_review_item(log_id):
    """
    Resolve an enrichment review item.

    Body:
        {
            'account_id': '0379481',  # Selected account (if manual resolution)
            'notes': 'Admin notes...'
        }
    """
    from flask import g

    log = db.session.query(EnrichmentReviewLog).get(log_id)
    if not log:
        return jsonify({'error': 'Review item not found'}), 404

    if log.resolved_at:
        return jsonify({'error': 'Already resolved'}), 400

    data = request.get_json() or {}
    account_id = data.get('account_id')
    notes = data.get('notes', '')

    # Mark as resolved
    from datetime import datetime
    log.resolved_at = datetime.now()
    log.resolved_by = g.user.id if hasattr(g, 'user') and g.user else None
    log.resolution_notes = notes

    # If account_id provided, save the enrichment
    if account_id and log.enrichment_type == 'wake_re':
        url = build_account_url(account_id)

        enrichment = db.session.query(Enrichment).filter_by(case_id=log.case_id).first()
        if not enrichment:
            enrichment = Enrichment(case_id=log.case_id)
            db.session.add(enrichment)

        enrichment.wake_re_account = account_id
        enrichment.wake_re_url = url
        enrichment.wake_re_enriched_at = datetime.now()
        enrichment.wake_re_error = None

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Resolved review item {log_id}',
        'url': url if account_id else None,
    })


@bp.route('/api/enrichments/status/<int:case_id>', methods=['GET'])
@require_auth
def get_enrichment_status(case_id):
    """Get enrichment status for a case."""
    enrichment = db.session.query(Enrichment).filter_by(case_id=case_id).first()

    if not enrichment:
        return jsonify({
            'case_id': case_id,
            'wake_re': None,
        })

    return jsonify({
        'case_id': case_id,
        'wake_re': {
            'url': enrichment.wake_re_url,
            'account': enrichment.wake_re_account,
            'enriched_at': enrichment.wake_re_enriched_at.isoformat() if enrichment.wake_re_enriched_at else None,
            'error': enrichment.wake_re_error,
        },
    })
```

**Step 2: Register blueprint in app.py**

Add to `web_app/app.py` in the blueprint registration section:

```python
from web_app.api import enrichments
app.register_blueprint(enrichments.bp)
```

**Step 3: Verify API loads**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from web_app.api.enrichments import bp; print('Enrichments API loaded')"
```

Expected: `Enrichments API loaded`

**Step 4: Commit**

```bash
git add web_app/api/enrichments.py web_app/app.py
git commit -m "feat: add enrichment API endpoints"
```

---

## Task 9: Dashboard Integration

**Files:**
- Modify: `web_app/api/cases.py` (add wake_re_url to upset-bids response)
- Modify: `frontend/src/pages/Dashboard.jsx` (add Property Info quicklink)

**Step 1: Update upset-bids API**

In `web_app/api/cases.py`, find the `get_upset_bids` function and modify to include enrichment data:

```python
# Add import at top of file
from enrichments.common.models import Enrichment

# In get_upset_bids function, modify the query to join with enrichments
# and include wake_re_url in the response
```

Add to the query:
```python
query = db.session.query(Case, Enrichment.wake_re_url).outerjoin(
    Enrichment, Case.id == Enrichment.case_id
).filter(Case.classification == 'upset_bid')
```

Add to each result dict:
```python
'wake_re_url': wake_re_url,
```

**Step 2: Update Dashboard.jsx**

In the Links column render function, update the Property Info icon to use `wake_re_url`:

```jsx
<Tooltip title={record.wake_re_url ? "Wake County Property" : "Coming soon"}>
    <a
        href={record.wake_re_url || '#'}
        target="_blank"
        rel="noopener noreferrer"
        style={{ opacity: record.wake_re_url ? 1 : 0.3 }}
        onClick={(e) => !record.wake_re_url && e.preventDefault()}
    >
        <PropertyInfoIcon />
    </a>
</Tooltip>
```

**Step 3: Test the frontend**

Start servers and verify the dashboard loads with the new column.

**Step 4: Commit**

```bash
git add web_app/api/cases.py frontend/src/pages/Dashboard.jsx
git commit -m "feat: integrate Wake RE URLs into dashboard"
```

---

## Task 10: Backfill Script

**Files:**
- Create: `scripts/backfill_wake_enrichments.py`

**Step 1: Write the backfill script**

```python
#!/usr/bin/env python
"""
Backfill Wake RE enrichments for existing upset_bid cases.

Usage:
    PYTHONPATH=$(pwd) python scripts/backfill_wake_enrichments.py [--dry-run]
"""

import argparse
import logging
import sys
import time

# Add project root to path
sys.path.insert(0, '/home/ahn/projects/nc_foreclosures')

from database.db import db
from database.models import Case
from enrichments.common.models import Enrichment
from enrichments.wake_re import enrich_case
from enrichments.wake_re.config import COUNTY_CODE
from web_app.app import create_app


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def get_cases_needing_enrichment():
    """Get Wake County upset_bid cases without enrichment."""
    # Subquery for cases with existing enrichment
    enriched_case_ids = db.session.query(Enrichment.case_id).filter(
        Enrichment.wake_re_url.isnot(None)
    ).subquery()

    # Get cases without enrichment
    cases = db.session.query(Case).filter(
        Case.county_code == COUNTY_CODE,
        Case.classification == 'upset_bid',
        ~Case.id.in_(enriched_case_ids),
    ).order_by(Case.next_bid_deadline.asc()).all()

    return cases


def run_backfill(dry_run: bool = False):
    """Run the backfill process."""
    cases = get_cases_needing_enrichment()

    logger.info(f"Found {len(cases)} Wake County upset_bid cases needing enrichment")

    if dry_run:
        for case in cases:
            logger.info(f"Would enrich: {case.case_number} (parcel={case.parcel_id}, addr={case.property_address})")
        return

    success_count = 0
    error_count = 0
    review_count = 0

    for i, case in enumerate(cases, 1):
        logger.info(f"[{i}/{len(cases)}] Enriching {case.case_number}...")

        try:
            result = enrich_case(case.id)

            if result.get('success'):
                success_count += 1
                logger.info(f"  ✓ Success: {result.get('url')}")
            elif result.get('review_needed'):
                review_count += 1
                logger.warning(f"  ! Needs review: {result.get('error')}")
            else:
                error_count += 1
                logger.error(f"  ✗ Error: {result.get('error')}")

            # Rate limiting - be nice to Wake County servers
            time.sleep(1)

        except Exception as e:
            error_count += 1
            logger.exception(f"  ✗ Exception: {e}")

    logger.info(f"\nBackfill complete:")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Needs review: {review_count}")
    logger.info(f"  Errors: {error_count}")


def main():
    parser = argparse.ArgumentParser(description='Backfill Wake RE enrichments')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        run_backfill(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
```

**Step 2: Make executable**

```bash
chmod +x scripts/backfill_wake_enrichments.py
```

**Step 3: Test with dry run**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python scripts/backfill_wake_enrichments.py --dry-run
```

Expected: Lists cases that would be enriched without making changes.

**Step 4: Commit**

```bash
git add scripts/backfill_wake_enrichments.py
git commit -m "feat: add backfill script for Wake RE enrichments"
```

---

## Task 11: Classifier Integration (Async Trigger)

**Files:**
- Modify: `extraction/classifier.py` (add async enrichment trigger)

**Step 1: Add enrichment trigger**

In `extraction/classifier.py`, find where classification changes are applied and add:

```python
# Add import at top
from threading import Thread

# After classification change is committed, add:
def _trigger_wake_enrichment_async(case_id: int):
    """Trigger Wake RE enrichment in background thread."""
    try:
        from enrichments.wake_re import enrich_case
        enrich_case(case_id)
    except Exception as e:
        logger.error(f"Async enrichment failed for case {case_id}: {e}")

# In the classification change logic:
if new_classification == 'upset_bid' and case.county_code == '910':
    Thread(target=_trigger_wake_enrichment_async, args=(case.id,), daemon=True).start()
    logger.info(f"Queued Wake RE enrichment for case {case.case_number}")
```

**Step 2: Test the trigger**

Manually run classifier on a test case and verify enrichment is triggered.

**Step 3: Commit**

```bash
git add extraction/classifier.py
git commit -m "feat: trigger async Wake RE enrichment on upset_bid promotion"
```

---

## Summary

This implementation plan covers:

1. **Database migrations** - Tables for enrichments and review queue
2. **SQLAlchemy models** - Enrichment and EnrichmentReviewLog
3. **Address parser** - Parse addresses into components for search
4. **URL builder** - Construct Wake County RE URLs from parcel IDs and addresses
5. **Scraper** - Fetch and parse Wake County RE pages
6. **Base enricher** - Abstract base class for extensibility
7. **Wake RE enricher** - Main entry point with parcel ID and address fallback
8. **API endpoints** - Manual trigger, review queue, resolution
9. **Dashboard integration** - Show Wake RE URLs in quicklinks
10. **Backfill script** - Enrich existing upset_bid cases
11. **Classifier integration** - Async trigger on upset_bid promotion

**Estimated tasks:** 11 main tasks, ~50 individual steps

---

**Plan complete and saved to `docs/plans/2025-12-20-wake-re-enrichment-implementation.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
