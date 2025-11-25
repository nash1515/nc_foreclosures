"""Integration tests for Phase 1 Foundation."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import test_connection
from scraper.vpn_manager import get_current_ip, is_vpn_connected
from scraper.captcha_solver import CaptchaSolver
from common.county_codes import get_county_code, get_search_text
from common.logger import setup_logger

logger = setup_logger(__name__)


def test_database_connection():
    """Test database connection."""
    logger.info("Testing database connection...")
    assert test_connection(), "Database connection failed"
    logger.info("✓ Database connection successful")


def test_vpn_manager():
    """Test VPN manager."""
    logger.info("Testing VPN manager...")

    # Test getting current IP
    current_ip = get_current_ip()
    assert current_ip is not None, "Failed to get current IP"
    logger.info(f"  Current IP: {current_ip}")

    # Test VPN check
    is_connected, ip, msg = is_vpn_connected()
    logger.info(f"  VPN connected: {is_connected}")
    logger.info(f"  Message: {msg}")

    logger.info("✓ VPN manager working")


def test_capsolver_init():
    """Test CapSolver initialization."""
    logger.info("Testing CapSolver initialization...")

    solver = CaptchaSolver()
    assert solver is not None, "Failed to initialize CapSolver"
    assert solver.api_key is not None, "API key not set"

    logger.info("✓ CapSolver initialized")


def test_county_codes():
    """Test county code utilities."""
    logger.info("Testing county codes...")

    # Test code lookup
    wake_code = get_county_code('wake')
    assert wake_code == '910', f"Expected '910', got '{wake_code}'"

    # Test search text generation
    search_text = get_search_text('wake', 2024)
    assert search_text == '24SP*', f"Expected '24SP*', got '{search_text}'"

    logger.info("✓ County codes working")


def run_all_tests():
    """Run all integration tests."""
    logger.info("=" * 60)
    logger.info("PHASE 1 INTEGRATION TESTS")
    logger.info("=" * 60)

    tests = [
        ("Database Connection", test_database_connection),
        ("VPN Manager", test_vpn_manager),
        ("CapSolver Initialization", test_capsolver_init),
        ("County Codes", test_county_codes)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            logger.error(f"✗ {name} failed: {e}")
            failed += 1

    logger.info("=" * 60)
    logger.info(f"Tests passed: {passed}/{len(tests)}")
    logger.info(f"Tests failed: {failed}/{len(tests)}")
    logger.info("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
