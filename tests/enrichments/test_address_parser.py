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
