from typing import Any, Optional
from pydantic import BaseModel, Field

class OCRResult(BaseModel):
    """
    Standard OCR output used across the system.
    """
    text: str = Field(..., description="Cleaned OCR text, ready for LLM")
    raw_data: Optional[Any] = Field(None, description="Backend-specific raw OCR output")
    success: bool
    error: Optional[str] = None
    backend: str = Field(..., description="The OCR engine used (e.g., rapidocr, tesseract)")
