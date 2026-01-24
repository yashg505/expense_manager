import re
import sys

from PIL import Image
import pytesseract

from expense_manager.logger import get_logger
from expense_manager.exception import CustomException
from expense_manager.models import OCRResult
from expense_manager.utils.artifacts_gcs import ensure_local_artifact

logger = get_logger(__name__)

# ---------------------------------------------------------------------
# RapidOCR backend
# ---------------------------------------------------------------------

_RAPIDOCR_ENGINE = None

def _load_rapidocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
        return RapidOCR()
    except Exception as e:
        logger.error("Failed to load RapidOCR engine: %s", e)
        raise CustomException(e, sys)

def rapidocr_backend(image_path: str):
    """
    Run RapidOCR on an image file path.
    Output format: [ [bbox, text, confidence], ... ]
    """
    global _RAPIDOCR_ENGINE
    try:
        if _RAPIDOCR_ENGINE is None:
            _RAPIDOCR_ENGINE = _load_rapidocr_engine()

        # RapidOCR returns (result, elapsed_time)
        result, _ = _RAPIDOCR_ENGINE(image_path)
        return result
    except Exception as e:
        raise CustomException(e, sys)

# ---------------------------------------------------------------------
# Tesseract backend
# ---------------------------------------------------------------------

def tesseract_backend(image_path: str):
    """Run Tesseract on an image file path."""
    try:
        with Image.open(image_path) as img:
            image = img.convert("RGB")
            return pytesseract.image_to_string(image)
    except Exception as e:
        raise CustomException(e, sys)

# ---------------------------------------------------------------------
# OCR Handler
# ---------------------------------------------------------------------

class OCRHandler:
    """
    OCRHandler converts an image file into clean, LLM-ready text.
    
    Usage:
        ocr = OCRHandler(backend="rapidocr")
        result = ocr.run("data/receipt_01.png")
    """

    def __init__(self, backend: str = "rapidocr"):
        self.backends = {
            "rapidocr": rapidocr_backend,
            "tesseract": tesseract_backend,
        }

        if backend not in self.backends:
            raise CustomException(
                f"Unsupported OCR backend '{backend}'. Available: {list(self.backends.keys())}",
                sys
            )

        self.backend_name = backend
        self.ocr_fn = self.backends[backend]
        logger.info("OCRHandler initialized with backend='%s'", backend)

    def run(self, image_path: str) -> OCRResult:
        """
        Safe execution boundary: catches all errors and returns an OCRResult.
        """
        try:
            if not image_path:
                raise FileNotFoundError("Image path is empty")

            local_path = ensure_local_artifact(image_path)

            raw_output = self.ocr_fn(local_path)

            if raw_output is None:
                raise ValueError("OCR engine returned None")

            # Extract text from the specific backend structure
            text = self._format_output(raw_output)
            
            # Clean text for LLM ingestion
            clean_text = self._clean_for_llm(text)

            if not clean_text.strip():
                logger.warning("OCR successful but no text was detected in: %s", image_path)

            return OCRResult(
                text=clean_text,
                raw_data=raw_output,
                success=True,
                backend=self.backend_name
            )

        except Exception as e:
            err_msg = str(e)
            logger.error("OCR failed for %s: %s", image_path, err_msg)
            return OCRResult(
                text="",
                raw_data=None,
                success=False,
                error=err_msg,
                backend=self.backend_name
            )

    def _format_output(self, raw) -> str:
        """
        Normalize different backend outputs into a single string.
        """
        # RapidOCR list-based output
        if isinstance(raw, list):
            lines = []
            for entry in raw:
                # Structure: [bbox, text, confidence]
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    # In some versions, text is at entry[1], in others it's nested
                    txt = entry[1]
                    if txt:
                        lines.append(str(txt))
            return "\n".join(lines)

        # Tesseract/String output
        return str(raw)

    def _clean_for_llm(self, text: str) -> str:
        """
        Sanitize text: remove excessive whitespace and noise.
        """
        if not text:
            return ""

        # Normalize whitespace (tabs/spaces to single space)
        text = re.sub(r"[ \t]+", " ", text)
        
        # Normalize newlines (max 2 consecutive)
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        # Final trim
        return text.strip()
    
# Example usage:
if __name__ == "__main__":
    ocr = OCRHandler(backend="rapidocr")
    result = ocr.run(r"artifacts/images/f1f0da5a-34df-435c-aed3-c5a00427ef0c.jpeg")
    if result.success:
        print("OCR Text:\n", result.text)
    else:
        print("OCR Failed:", result.error)