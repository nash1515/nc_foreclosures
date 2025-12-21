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
