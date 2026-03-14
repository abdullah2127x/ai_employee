"""
logging_utils.py - Logging utilities for AI Employee

Provides structured logging with file and console output.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging with both file and console handlers.

    Args:
        log_dir: Directory to store log files
        level: Logging level (default: INFO)

    Returns:
        Configured root logger
    """
    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create logs directory
    log_file = log_dir / f"orchestrator_{datetime.now().strftime('%Y%m%d')}.log"

    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers = []

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler (with color support on Windows)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Log startup
    logger.info("=" * 70)
    logger.info(f"AI Employee Orchestrator Starting")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 70)

    return logger
