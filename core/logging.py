import logging
import sys
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path

# --- Constants ---
LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'
LOG_FILE = LOG_DIR / 'app.log'
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

class JsonFormatter(logging.Formatter):
    """
    Formats log records as a JSON string.
    """
    def format(self, record):
        log_object = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_object['exc_info'] = self.formatException(record.exc_info)

        return json.dumps(log_object)

def setup_logging(log_level=logging.INFO):
    """
    Configures logging.
    - Console: Human-readable plain text.
    - File: Machine-readable JSON, with rotation.
    """
    LOG_DIR.mkdir(exist_ok=True)

    # --- Root Logger Configuration ---
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # --- Formatters ---
    plain_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    json_formatter = JsonFormatter()

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(plain_formatter)

    # --- Rotating File Handler (JSON) ---
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(json_formatter)

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
