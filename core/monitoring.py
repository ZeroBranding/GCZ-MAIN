import logging
from prometheus_client import start_http_server, Counter, Histogram

# --- Metric Definitions ---

# A counter to track the total number of goals (commands) received by the bot.
# The 'goal_type' label will distinguish between different commands like '/img', '/upscale', etc.
GRAPH_GOALS_TOTAL = Counter(
    "graph_goals_total",
    "Total number of goals processed by the graph, labeled by type.",
    ["goal_type"]
)

# A histogram to measure the duration of a full graph session, from start to finish.
# This helps understand the overall performance and identify slow runs.
GRAPH_SESSION_DURATION_MS = Histogram(
    "graph_session_duration_ms",
    "Duration of a full graph execution session in milliseconds.",
    buckets=(100, 500, 1000, 2000, 5000, 10000, 30000, 60000) # Buckets from 100ms to 1min
)

# A histogram to measure the duration of individual tool calls (steps) within the graph.
# This is crucial for identifying which specific tool or step is a bottleneck.
ENGINE_STEP_DURATION_MS = Histogram(
    "engine_step_duration_ms",
    "Duration of an individual engine step (tool call) in milliseconds.",
    ["step_name"],
    buckets=(50, 100, 250, 500, 1000, 2500, 5000, 10000) # Buckets from 50ms to 10s
)

# A counter for the number of steps that result in an error.
ENGINE_STEP_ERRORS_TOTAL = Counter(
    "engine_step_errors_total",
    "Total number of errors encountered during engine step execution.",
    ["step_name"]
)

# --- Server Control ---

def start_metrics_server(port: int = 8001, addr: str = "127.0.0.1"):
    """
    Starts the Prometheus metrics HTTP server in a background thread.

    Args:
        port: The port to listen on.
        addr: The address to bind to. Defaults to '127.0.0.1' to prevent
              external exposure.
    """
    try:
        start_http_server(port, addr=addr)
        logging.getLogger(__name__).info(f"Prometheus metrics server started on http://{addr}:{port}/metrics")
    except OSError as e:
        logging.getLogger(__name__).error(f"Failed to start Prometheus server on port {port}: {e}. "
                                           "Metrics will not be available. Is another process using the port?")
