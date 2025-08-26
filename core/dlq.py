import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

DLQ_DIR = Path.cwd() / "data" / "dlq"
DLQ_DIR.mkdir(parents=True, exist_ok=True)

def write_to_dlq(session_id: str, step_name: str, context: dict, error: str):
    """
    Writes a failed step to the Dead-Letter Queue.

    Args:
        session_id: The ID of the session/run.
        step_name: The name of the step that failed.
        context: The context or input to the step.
        error: The error message.
    """
    try:
        timestamp = datetime.now().isoformat().replace(":", "-")
        filename = f"{session_id}_{step_name}_{timestamp}.json"
        filepath = DLQ_DIR / filename

        dlq_item = {
            "session_id": session_id,
            "step_name": step_name,
            "context": context,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dlq_item, f, indent=2, ensure_ascii=False)

        logger.warning(f"Step '{step_name}' for session '{session_id}' failed and was written to DLQ: {filepath}")

    except Exception as e:
        logger.error(f"Failed to write to DLQ: {e}", exc_info=True)

def list_dlq_items() -> list:
    """Lists all items in the DLQ."""
    items = []
    for filepath in DLQ_DIR.glob("*.json"):
        with open(filepath, "r", encoding="utf-8") as f:
            items.append(json.load(f))
    return items
