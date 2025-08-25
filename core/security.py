import logging
from enum import Enum
from datetime import datetime
from typing import Dict, List
from pydantic import BaseModel

class Role(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

class AuditLogEntry(BaseModel):
    timestamp: datetime
    user: str
    action: str
    resource: str
    status: str

class RBACService:
    def __init__(self):
        self.roles: Dict[str, List[str]] = {
            "admin": ["*"],
            "editor": ["workflow:execute", "document:read", "document:write"],
            "viewer": ["document:read"]
        }
        self.audit_log: List[AuditLogEntry] = []
        self.logger = logging.getLogger(__name__)

    def check_permission(self, user_role: Role, action: str, resource: str) -> bool:
        """Überprüft Berechtigungen und loggt den Zugriff"""
        allowed = any(
            perm == "*" or perm == f"{resource}:{action}"
            for perm in self.roles.get(user_role.value, [])
        )
        
        self.audit_log.append(
            AuditLogEntry(
                timestamp=datetime.now(),
                user=user_role.value,
                action=action,
                resource=resource,
                status="ALLOWED" if allowed else "DENIED"
            )
        )
        
        if not allowed:
            self.logger.warning(f"Zugriff verweigert für {user_role.value} auf {resource}:{action}")
        
        return allowed

    def get_audit_logs(self, limit: int = 100) -> List[AuditLogEntry]:
        """Gibt die neuesten Audit-Logs zurück"""
        return sorted(self.audit_log, key=lambda x: x.timestamp, reverse=True)[:limit]
