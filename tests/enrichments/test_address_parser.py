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

    def test_address_with_north_in_name(self):
        # "North" is kept as part of street name since full words are ambiguous
        # (could be directional or part of name like "North Hills" or "South Ridge")
        result = parse_address("500 North Hills Drive, Raleigh, NC 27609")
        assert result['stnum'] == '500'
        assert result['prefix'] is None
        assert result['name'] == 'NORTH HILLS'

    def test_address_with_n_prefix(self):
        # Abbreviated "N." is unambiguously a directional prefix
        result = parse_address("500 N. Hills Drive, Raleigh, NC 27609")
        assert result['stnum'] == '500'
        assert result['prefix'] == 'N'
        assert result['name'] == 'HILLS'

    def test_address_with_se_prefix(self):
        # Compound directional prefixes like SE are unambiguous
        result = parse_address("303 SE Maynard Road, Cary, NC 27511")
        assert result['stnum'] == '303'
        assert result['prefix'] == 'SE'
        assert result['name'] == 'MAYNARD'

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

    def test_extracts_south_abbreviated(self):
        assert extract_prefix("S. Salem") == "S"

    def test_extracts_north_abbreviated(self):
        assert extract_prefix("N Main") == "N"

    def test_extracts_east_abbreviated(self):
        assert extract_prefix("E Main") == "E"

    def test_extracts_west_abbreviated(self):
        assert extract_prefix("W. Oak") == "W"

    def test_extracts_se_compound(self):
        assert extract_prefix("SE Maynard") == "SE"

    def test_extracts_nw_compound(self):
        assert extract_prefix("NW Front") == "NW"

    def test_no_prefix_full_word_north(self):
        # Full words like "North" are ambiguous (could be part of street name)
        assert extract_prefix("North Hills") is None

    def test_no_prefix_full_word_south(self):
        assert extract_prefix("South Ridge") is None

    def test_no_prefix(self):
        assert extract_prefix("Main") is None

    def test_no_prefix_regular_word(self):
        assert extract_prefix("Sweet Laurel") is None
