
import os
from pathlib import Path
from typing import Optional, Tuple
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfReader

class DocumentService:
    def __init__(self, temp_dir: str = "temp_docs"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extrahiert Text aus PDF mit OCR-Fallback."""
        text = ""
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception:
            # Fallback auf OCR, falls direktes Extrahieren fehlschlägt
            pass

        if text.strip():
            return text
        
        # OCR-Fallback
        return self._ocr_pdf(pdf_path)

    def _ocr_pdf(self, pdf_path: str) -> str:
        """Verwendet OCR für PDFs ohne durchsuchbaren Text"""
        images = convert_from_path(pdf_path)
        text_parts = []
        
        for i, img in enumerate(images):
            img_path = self.temp_dir / f"page_{i}.jpg"
            img.save(img_path, 'JPEG')
            text = pytesseract.image_to_string(img_path, lang='deu+eng')
            text_parts.append(text)
            os.remove(img_path)
            
        return "\n".join(text_parts)

    def extract_metadata(self, pdf_path: str) -> dict:
        """Extrahiert Metadaten aus PDF."""
        reader = PdfReader(pdf_path)
        meta = reader.metadata
        return {
            'title': meta.title or '',
            'author': meta.author or '',
            'pages': len(reader.pages)
        }
