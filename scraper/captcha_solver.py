"""CAPTCHA solving using CapSolver API."""

import time
import capsolver
from common.config import config
from common.logger import setup_logger

logger = setup_logger(__name__)

# Set CapSolver API key globally
capsolver.api_key = config.CAPSOLVER_API_KEY


class CaptchaSolver:
    """Wrapper for CapSolver API to solve reCAPTCHA."""

    def __init__(self):
        """Initialize CapSolver client."""
        if not config.CAPSOLVER_API_KEY:
            raise ValueError("CAPSOLVER_API_KEY not configured")

        capsolver.api_key = config.CAPSOLVER_API_KEY
        logger.info("CapSolver client initialized")

    def solve_recaptcha_v2(self, page_url, site_key, max_retries=3):
        """
        Solve reCAPTCHA v2.

        Args:
            page_url: URL of the page with CAPTCHA
            site_key: reCAPTCHA site key
            max_retries: Maximum number of retry attempts

        Returns:
            str: CAPTCHA solution token, or None if failed

        Raises:
            Exception: If all retry attempts fail
        """
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Solving reCAPTCHA (attempt {attempt}/{max_retries})...")
                logger.debug(f"Page URL: {page_url}")
                logger.debug(f"Site key: {site_key}")

                # Solve CAPTCHA using CapSolver
                solution = capsolver.solve({
                    "type": "ReCaptchaV2TaskProxyLess",
                    "websiteURL": page_url,
                    "websiteKey": site_key
                })

                logger.debug(f"Solution received: {solution}")

                if solution and 'gRecaptchaResponse' in solution:
                    token = solution['gRecaptchaResponse']
                    logger.info(f"✓ CAPTCHA solved successfully (attempt {attempt})")
                    logger.debug(f"Token: {token[:50]}...")
                    return token
                else:
                    logger.warning(f"No solution received (attempt {attempt})")

            except Exception as e:
                logger.error(f"CAPTCHA solving failed (attempt {attempt}): {e}")

                if attempt < max_retries:
                    wait_time = attempt * 2  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    raise Exception(f"Failed to solve CAPTCHA after {max_retries} attempts")

        return None


# Singleton instance
_solver = None


def get_solver():
    """Get or create CapSolver instance."""
    global _solver
    if _solver is None:
        _solver = CaptchaSolver()
    return _solver


def solve_recaptcha(page_url, site_key):
    """
    Convenience function to solve reCAPTCHA.

    Args:
        page_url: URL of the page with CAPTCHA
        site_key: reCAPTCHA site key

    Returns:
        str: CAPTCHA solution token
    """
    solver = get_solver()
    return solver.solve_recaptcha_v2(page_url, site_key)


if __name__ == '__main__':
    # Test CapSolver configuration
    print("Testing CapSolver configuration...")
    try:
        solver = CaptchaSolver()
        print("✓ CapSolver initialized successfully")
        print(f"API Key configured: {config.CAPSOLVER_API_KEY[:20]}...")
    except Exception as e:
        print(f"✗ CapSolver initialization failed: {e}")
