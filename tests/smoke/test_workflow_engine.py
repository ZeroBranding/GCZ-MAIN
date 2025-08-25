import pytest
from core.workflows.engine import WorkflowEngine

@pytest.mark.asyncio
async def test_workflow_engine_initialization():
    """Testet, ob die WorkflowEngine erfolgreich initialisiert werden kann."""
    try:
        engine = WorkflowEngine()
        assert engine is not None, "Engine konnte nicht initialisiert werden."
        assert engine.document_service is not None, "DocumentService wurde nicht geladen."
    except Exception as e:
        pytest.fail(f"Initialisierung der WorkflowEngine fehlgeschlagen: {e}")

@pytest.mark.asyncio
async def test_load_non_existent_workflow():
    """Testet, ob das Laden eines nicht existierenden Workflows korrekt fehlschlägt."""
    engine = WorkflowEngine()
    with pytest.raises(FileNotFoundError):
        await engine._load_workflow_by_id("non_existent_workflow")
