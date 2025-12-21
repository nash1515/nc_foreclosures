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
