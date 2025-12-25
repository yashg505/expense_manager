from dataclasses import dataclass
from typing import Callable, Dict, Optional
from PIL import Image
import pytesseract
from src.logger import get_logger
from src.exception import CustomException
import sys
import re

logger = get_logger(__name__)


# ---------------------------------------------------------------------
# OCR Result Dataclass
# ---------------------------------------------------------------------
@dataclass
class OCRResult:
    text: str
    success: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------
# Backend OCR Functions (Small, Direct, Easy)
# ---------------------------------------------------------------------
def tesseract_ocr(image: Image.Image) -> str:
    """Tesseract backend."""
    return pytesseract.image_to_string(image)


def openai_ocr(image: Image.Image) -> str:
    """
    Future backend: OpenAI Vision (placeholder).

    """
    raise NotImplementedError("OpenAI OCR is not implemented yet.")


# ---------------------------------------------------------------------
# Registry (Plug-and-Play Backends)
# ---------------------------------------------------------------------
OCR_BACKENDS: Dict[str, Callable[[Image.Image], str]] = {
    "tesseract": tesseract_ocr,
}


# ---------------------------------------------------------------------
# OCR Handler (Orchestrator)
# ---------------------------------------------------------------------
class OCRHandler:
    """
    OCR orchestrator.

    Usage:
        ocr = OCRHandler("tesseract")
        result = ocr.run(image)
    """

    def __init__(self, backend: str = "tesseract"):
        if backend not in OCR_BACKENDS:
            raise ValueError(f"Unknown OCR backend: {backend}")

        self.backend = backend
        self.ocr_fn = OCR_BACKENDS[backend]

        logger.info("OCRHandler initialized with backend=%s", backend)

    # -----------------------------------------------------------------
    def run(self, image: Image.Image) -> OCRResult:
        """Runs OCR using the selected backend and returns normalized text."""
        try:
            raw_text = self.ocr_fn(image)
            clean_text = self._clean(raw_text)

            return OCRResult(
                text=clean_text,
                success=True
            )

        except Exception as e:
            logger.error("OCR backend '%s' failed: %s", self.backend, e)
            return OCRResult(
                text="",
                success=False,
                error=str(e)
            )

    # -----------------------------------------------------------------
    def _clean(self, text: str) -> str:
        """Normalize spacing and newlines."""
        text = text.strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text
