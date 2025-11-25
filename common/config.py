"""Configuration management for NC Foreclosures project."""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration loaded from environment variables."""

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://nc_user:nc_password@localhost/nc_foreclosures')

    # CapSolver
    CAPSOLVER_API_KEY = os.getenv('CAPSOLVER_API_KEY')

    # VPN
    VPN_BASELINE_IP = os.getenv('VPN_BASELINE_IP')
    VPN_AUTO_START = os.getenv('VPN_AUTO_START', 'false').lower() == 'true'
    SUDO_PASSWORD = os.getenv('SUDO_PASSWORD', None)

    # Storage
    PDF_STORAGE_PATH = os.getenv('PDF_STORAGE_PATH', './data/pdfs')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        errors = []

        if not cls.CAPSOLVER_API_KEY:
            errors.append("CAPSOLVER_API_KEY not set in environment")

        if not cls.VPN_BASELINE_IP:
            errors.append("VPN_BASELINE_IP not set in environment")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        return True

    @classmethod
    def get_pdf_path(cls, county, case_number):
        """Get the file path for storing a case's PDFs."""
        base_path = Path(cls.PDF_STORAGE_PATH)
        case_path = base_path / county.lower() / case_number
        case_path.mkdir(parents=True, exist_ok=True)
        return case_path


# Create a singleton instance
config = Config()
