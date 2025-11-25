"""VPN verification and management before scraping."""

import requests
import sys
import subprocess
import time
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


def start_vpn(sudo_password=None):
    """
    Start VPN connection using OpenVPN.

    Args:
        sudo_password: Optional sudo password. If None, will try without password.

    Returns:
        bool: True if VPN started successfully
    """
    vpn_config = "/home/ahn/frootvpn/United States - Virginia.ovpn"
    auth_file = "/home/ahn/frootvpn/auth.txt"
    log_file = "/tmp/openvpn.log"

    logger.info("Starting VPN connection...")

    try:
        if sudo_password:
            # Use sudo with password via stdin
            cmd = f'echo "{sudo_password}" | sudo -S openvpn --config "{vpn_config}" --auth-user-pass "{auth_file}" --daemon --log "{log_file}"'
        else:
            # Try without password (if sudo is configured for passwordless)
            cmd = f'sudo openvpn --config "{vpn_config}" --auth-user-pass "{auth_file}" --daemon --log "{log_file}"'

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info("VPN start command executed, waiting for connection...")
            # Wait for VPN to connect
            time.sleep(5)

            # Verify connection
            is_connected, current_ip, message = is_vpn_connected()
            if is_connected:
                logger.info(f"✓ VPN connected successfully: {current_ip}")
                return True
            else:
                logger.warning("VPN command succeeded but not yet connected, waiting longer...")
                time.sleep(10)
                is_connected, current_ip, message = is_vpn_connected()
                if is_connected:
                    logger.info(f"✓ VPN connected successfully: {current_ip}")
                    return True
                else:
                    logger.error(f"VPN failed to connect: {message}")
                    return False
        else:
            logger.error(f"Failed to start VPN: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("VPN start command timed out")
        return False
    except Exception as e:
        logger.error(f"Error starting VPN: {e}")
        return False


def verify_vpn_or_exit(auto_start=False, sudo_password=None):
    """
    Verify VPN is connected, optionally try to start it, exit if not connected.

    Args:
        auto_start: If True, attempt to start VPN if not connected
        sudo_password: Optional sudo password for VPN start

    This should be called at the start of any scraping operation.
    """
    logger.info("Verifying VPN connection...")

    is_connected, current_ip, message = is_vpn_connected()

    if not is_connected:
        if auto_start:
            logger.info("VPN not connected, attempting to start...")
            if start_vpn(sudo_password):
                logger.info("✓ VPN started and verified")
                return get_current_ip()

        logger.error("=" * 60)
        logger.error("VPN VERIFICATION FAILED!")
        logger.error(message)
        logger.error("=" * 60)
        logger.error("Please connect to FROOT VPN before running the scraper.")
        logger.error("Command: cd ~/frootvpn && sudo openvpn --config 'United States - Virginia.ovpn' --auth-user-pass auth.txt --daemon --log /tmp/openvpn.log")
        logger.error("Exiting for safety.")
        sys.exit(1)

    logger.info("✓ VPN verification passed")
    return current_ip


if __name__ == '__main__':
    # Test VPN verification
    print("Testing VPN verification...")
    verify_vpn_or_exit()
    print("VPN test passed!")
