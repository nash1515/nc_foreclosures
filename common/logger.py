"""Logging configuration for NC Foreclosures project."""

import logging
import sys
from common.config import config


def setup_logger(name: str, level: str = None) -> logging.Logger:
    """
    Set up a logger with consistent formatting.

    Args:
        name: Name of the logger (usually __name__ from calling module)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    if level is None:
        level = config.LOG_LEVEL

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Avoid adding handlers multiple times
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))

        # Format: timestamp - name - level - message
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger


# Create a default logger for common module
logger = setup_logger(__name__)
