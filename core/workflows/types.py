from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StepType(str, Enum):
    DOCUMENT_EXTRACT = "document_extract"
    DOCUMENT_CONVERT = "document_convert"

class DocumentStepConfig(BaseModel):
    """Konfiguration für Dokumentenverarbeitungsschritte"""
    input_path: str
    output_path: Optional[str] = None
    extract_metadata: bool = True
    use_ocr: bool = False

class Step(BaseModel):
    name: str
    command: List[str]
    dependencies: Optional[List[str]] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    artifacts_in: List[str] = Field(default_factory=list)
    artifacts_out: List[str] = Field(default_factory=list)

class Workflow(BaseModel):
    name: str
    description: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    steps: List[Step]
