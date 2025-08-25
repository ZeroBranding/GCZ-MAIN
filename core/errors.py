class GCZError(Exception):
    """Base exception class for the German Code Zero AI project."""
    pass

class ConfigError(GCZError):
    """Raised when there is an error in a configuration file."""
    pass

class EnvError(GCZError):
    """Raised when a required environment variable is missing."""
    pass

class ExternalToolError(GCZError):
    """Raised when an external tool or service fails."""
    pass

class MCPError(GCZError):
    """Raised for errors related to the MCP client or servers."""
    pass
