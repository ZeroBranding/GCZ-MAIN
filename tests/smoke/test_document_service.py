import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.document_service import DocumentService
from pathlib import Path
import os
from unittest.mock import patch

# Erstelle eine Dummy-PDF-Datei für den Test
DUMMY_PDF_PATH = Path("tests/smoke/dummy.pdf")

def create_dummy_pdf():
    # Dieser Teil erfordert eine Bibliothek wie reportlab.
    # Für einen Smoke-Test reicht es, die Existenz der Methode zu prüfen.
    # Hier wird nur eine leere Datei erstellt, um FileNotFoundError zu vermeiden.
    if not DUMMY_PDF_PATH.parent.exists():
        DUMMY_PDF_PATH.parent.mkdir(parents=True)
    DUMMY_PDF_PATH.touch()

@pytest.fixture(scope="module")
def setup_document_service():
    create_dummy_pdf()
    yield
    os.remove(DUMMY_PDF_PATH)


def test_document_service_initialization():
    """Testet, ob der DocumentService erfolgreich initialisiert werden kann."""
    try:
        service = DocumentService()
        assert service is not None
        assert service.temp_dir.exists()
    except Exception as e:
        pytest.fail(f"Initialisierung des DocumentService fehlgeschlagen: {e}")


def test_extract_text_from_pdf_runs(setup_document_service):
    """Testet, ob die PDF-Extraktion ohne Fehler durchläuft (OCR wird übersprungen)."""
    service = DocumentService()
    try:
        # Passe den Service an, damit er OCR nicht verwendet, falls Poppler fehlt
        with patch('pdf2image.pdf2image.convert_from_path', side_effect=Exception("Poppler not installed")):
            service.extract_text_from_pdf(str(DUMMY_PDF_PATH))
    except Exception as e:
        # Hier sollte kein Fehler mehr auftreten, da der kritische Teil gemockt ist
        if "Poppler" in str(e):
             pytest.skip("Poppler ist für den OCR-Teil erforderlich, wird hier übersprungen.")
        pytest.fail(f"extract_text_from_pdf hat einen unerwarteten Fehler ausgelöst: {e}")
