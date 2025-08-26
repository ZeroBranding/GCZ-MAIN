import logging
import json
from datetime import datetime
import hashlib

# --- Audit Logger Setup ---
# We create a dedicated logger for audit trails to allow separate routing.
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False # Prevent audit logs from going to the main app logger

# Configure a specific handler for audit logs if not already configured
if not audit_logger.handlers:
    # In a real app, this could be a FileHandler, a SyslogHandler, or a custom handler
    # that sends logs to a dedicated security system (e.g., ELK, Splunk).
    # For this project, we'll log to a separate file.
    log_file = "logs/audit.log"
    handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)

def _hash_params(params: dict) -> str:
    """Creates a SHA256 hash of the parameters for auditing without logging secrets."""
    if not params:
        return ""

    # Create a stable string representation of the dictionary
    # Sorting ensures that {"a": 1, "b": 2} and {"b": 2, "a": 1} produce the same hash.
    stable_string = json.dumps(params, sort_keys=True)

    return hashlib.sha256(stable_string.encode('utf-8')).hexdigest()

def audit_tool_call(
    correlation_id: str,
    user_id: str,
    tool_name: str,
    params: dict,
    status: str, # "ALLOWED", "DENIED"
    message: str = ""
):
    """
    Logs a tool call attempt for auditing purposes.

    Args:
        correlation_id: A unique ID for the entire request/run.
        user_id: The ID of the user making the request.
        tool_name: The name of the tool or function being called.
        params: The parameters passed to the tool. These will be hashed.
        status: The result of the policy check ("ALLOWED" or "DENIED").
        message: Any additional information, like the reason for denial.
    """
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "tool_call_attempt",
            "correlation_id": correlation_id,
            "user_id": user_id,
            "tool_name": tool_name,
            "params_hash": _hash_params(params),
            "status": status,
            "message": message
        }

        # Use a structured format like JSON for easy parsing by log management systems.
        audit_logger.info(json.dumps(log_entry))

    except Exception as e:
        # We should not let audit logging failures crash the application.
        logging.getLogger(__name__).error(f"Failed to write audit log: {e}", exc_info=True)
