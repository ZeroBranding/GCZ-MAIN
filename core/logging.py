import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# --- Constants ---
LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'
LOG_FILE = LOG_DIR / 'app.log'
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

def setup_logging(log_level=logging.INFO):
    """
    Configures logging to both a rotating file and the console.
    """
    LOG_DIR.mkdir(exist_ok=True)

    # --- Root Logger Configuration ---
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # --- Formatter ---
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # --- Rotating File Handler ---
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # --- Add Handlers to Root Logger ---
    # Clear existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return root_logger

# --- Initial Setup ---
# Initialize logging when the module is imported
logger = setup_logging()

# Example usage:
if __name__ == '__main__':
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")
