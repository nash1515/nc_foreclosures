"""VPN verification before scraping."""

import requests
import sys
from common.config import config
from common.logger import setup_logger

logger = setup_logger(__name__)


def get_current_ip():
    """
    Get current public IP address.

    Returns:
        str: Current public IP address or None if failed
    """
    try:
        response = requests.get('https://ifconfig.me', timeout=10)
        response.raise_for_status()
        ip = response.text.strip()
        logger.debug(f"Current IP: {ip}")
        return ip
    except requests.RequestException as e:
        logger.error(f"Failed to get current IP: {e}")
        return None


def is_vpn_connected():
    """
    Check if VPN is connected by comparing current IP to baseline.

    Returns:
        tuple: (bool: is_connected, str: current_ip, str: message)
    """
    baseline_ip = config.VPN_BASELINE_IP

    if not baseline_ip:
        logger.error("VPN_BASELINE_IP not configured in .env")
        return False, None, "VPN_BASELINE_IP not configured"

    current_ip = get_current_ip()

    if not current_ip:
        return False, None, "Could not retrieve current IP"

    if current_ip == baseline_ip:
        msg = f"VPN NOT connected. Current IP ({current_ip}) matches baseline IP"
        logger.warning(msg)
        return False, current_ip, msg
    else:
        msg = f"VPN verified. Current IP: {current_ip} (baseline: {baseline_ip})"
        logger.info(msg)
        return True, current_ip, msg


def verify_vpn_or_exit():
    """
    Verify VPN is connected, exit if not.

    This should be called at the start of any scraping operation.
    """
    logger.info("Verifying VPN connection...")

    is_connected, current_ip, message = is_vpn_connected()

    if not is_connected:
        logger.error("=" * 60)
        logger.error("VPN VERIFICATION FAILED!")
        logger.error(message)
        logger.error("=" * 60)
        logger.error("Please connect to FROOT VPN before running the scraper.")
        logger.error("Exiting for safety.")
        sys.exit(1)

    logger.info("✓ VPN verification passed")
    return current_ip


if __name__ == '__main__':
    # Test VPN verification
    print("Testing VPN verification...")
    verify_vpn_or_exit()
    print("VPN test passed!")
