"""Logging utilities for LOG Server."""

import logging
from typing import Optional


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with proper configuration."""
    return logging.getLogger(name)


def log_info(message: str, extra: Optional[Dict] = None) -> None:
    """Log an informational message."""
    logger = get_logger(__name__)
    if extra:
        logger.info(f"{message} | {extra}")
    else:
        logger.info(message)


def log_debug(message: str, extra: Optional[Dict] = None) -> None:
    """Log a debug message."""
    logger = get_logger(__name__)
    if extra:
        logger.debug(f"{message} | {extra}")
    else:
        logger.debug(message)


def log_error(message: str, exception: Optional[Exception] = None) -> None:
    """Log an error message with optional exception."""
    logger = get_logger(__name__)
    if exception:
        logger.error(f"{message} | Error: {exception}", exc_info=True)
    else:
        logger.error(message)


def log_warning(message: str, extra: Optional[Dict] = None) -> None:
    """Log a warning message."""
    logger = get_logger(__name__)
    if extra:
        logger.warning(f"{message} | {extra}")
    else:
        logger.warning(message)
