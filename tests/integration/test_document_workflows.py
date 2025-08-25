import pytest
from pathlib import Path
from core.workflows.engine import WorkflowEngine
from core.workflows.types import Step, StepType, DocumentStepConfig

@pytest.fixture
def sample_pdf():
    return str(Path(__file__).parent / "test_data" / "sample.pdf")

@pytest.mark.asyncio
async def test_document_extraction(sample_pdf):
    """Testet PDF-Textextraktion in Workflows"""
    engine = WorkflowEngine()
    step = Step(
        name="test_extract",
        type=StepType.DOCUMENT_EXTRACT,
        config=DocumentStepConfig(
            input_path=sample_pdf,
            extract_metadata=True
        )
    )
    
    result = await engine.execute_step(step)
    assert "text" in result
    assert len(result["text"]) > 0
    assert "metadata" in result
    assert result["metadata"]["pages"] > 0
