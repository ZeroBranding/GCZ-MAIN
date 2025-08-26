from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """Status eines Plan-Steps."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ErrorSeverity(str, Enum):
    """Schweregrad von Fehlern."""
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class UserRole(str, Enum):
    """Benutzerrollen für Permissions."""
    USER = "user"
    ADMIN = "admin"
    GUEST = "guest"


class UserContext(BaseModel):
    """User-Kontext mit Permissions."""
    user_id: str
    username: str
    role: UserRole = UserRole.USER
    telegram_chat_id: Optional[int] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)


class PlanItem(BaseModel):
    """Ein Step im Execution-Plan."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    action: str  # "txt2img", "upscale", "upload", etc.
    params: Dict[str, Any]
    dependencies: List[str] = Field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    estimated_duration_s: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ErrorInfo(BaseModel):
    """Fehler-Information."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    step_id: Optional[str] = None
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = 0


class ArtifactInfo(BaseModel):
    """Information über generierte Artefakte."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    path: Path
    type: str  # "image", "video", "audio", "document"
    step_id: str
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StepResult(BaseModel):
    """Ergebnis eines ausgeführten Steps."""
    step_id: str
    status: StepStatus
    artifacts: List[ArtifactInfo] = Field(default_factory=list)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    execution_time_s: Optional[float] = None
    error: Optional[ErrorInfo] = None


class GraphState(BaseModel):
    """Hauptzustand des LangGraph-Workflows."""
    
    # Session Management
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # User Context
    user: UserContext
    
    # Goal & Planning
    goal: str  # Original user input: "/img a cat in space"
    plan: List[PlanItem] = Field(default_factory=list)
    current_step: int = 0
    
    # Execution State
    last_result: Optional[StepResult] = None
    artifacts: List[ArtifactInfo] = Field(default_factory=list)
    errors: List[ErrorInfo] = Field(default_factory=list)
    
    # Context & Metadata
    context: Dict[str, Any] = Field(default_factory=dict)
    
    # Status tracking
    is_completed: bool = False
    is_failed: bool = False
    retry_budget: int = 10
    used_retries: int = 0
    
    # Performance
    total_execution_time_s: Optional[float] = None
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True
        json_encoders = {
            Path: str,
            datetime: lambda v: v.isoformat(),
            UUID: str
        }
    
    def update_timestamp(self) -> None:
        """Aktualisiert den Timestamp."""
        self.updated_at = datetime.utcnow()
    
    def get_current_plan_item(self) -> Optional[PlanItem]:
        """Gibt das aktuelle Plan-Item zurück."""
        if 0 <= self.current_step < len(self.plan):
            return self.plan[self.current_step]
        return None
    
    def get_pending_steps(self) -> List[PlanItem]:
        """Gibt alle noch ausstehenden Steps zurück."""
        return [item for item in self.plan if item.status == StepStatus.PENDING]
    
    def get_failed_steps(self) -> List[PlanItem]:
        """Gibt alle fehlgeschlagenen Steps zurück."""
        return [item for item in self.plan if item.status == StepStatus.FAILED]
    
    def has_critical_errors(self) -> bool:
        """Prüft ob kritische Fehler vorliegen."""
        return any(error.severity == ErrorSeverity.CRITICAL for error in self.errors)
    
    def add_artifact(self, path: Path, artifact_type: str, step_id: str, **metadata) -> ArtifactInfo:
        """Fügt ein neues Artefakt hinzu."""
        artifact = ArtifactInfo(
            path=path,
            type=artifact_type,
            step_id=step_id,
            metadata=metadata
        )
        if path.exists():
            artifact.size_bytes = path.stat().st_size
        
        self.artifacts.append(artifact)
        self.update_timestamp()
        return artifact
    
    def add_error(self, message: str, severity: ErrorSeverity = ErrorSeverity.ERROR, 
                  step_id: Optional[str] = None, **details) -> ErrorInfo:
        """Fügt einen neuen Fehler hinzu."""
        error = ErrorInfo(
            step_id=step_id,
            severity=severity,
            message=message,
            details=details
        )
        self.errors.append(error)
        self.update_timestamp()
        return error
    
    def advance_step(self) -> bool:
        """Geht zum nächsten Step über. Returns True wenn weitere Steps vorhanden."""
        self.current_step += 1
        self.update_timestamp()
        return self.current_step < len(self.plan)
    
    def can_retry(self) -> bool:
        """Prüft ob noch Retry-Budget vorhanden ist."""
        return self.used_retries < self.retry_budget and not self.has_critical_errors()