import pytest
from unittest.mock import MagicMock, patch
from expense_manager.components.ocr_handler import OCRHandler
from expense_manager.models import OCRResult

@pytest.fixture
def mock_rapidocr():
    with patch("expense_manager.components.ocr_handler._RAPIDOCR_ENGINE") as mock_engine:
        # If _RAPIDOCR_ENGINE is None, the code loads it. We might need to patch _load_rapidocr_engine or the class import.
        pass
    # Better to patch the load function or the class
    pass

def test_ocr_handler_init_valid():
    with patch("expense_manager.components.ocr_handler.rapidocr_backend"):
        ocr = OCRHandler(backend="rapidocr")
        assert ocr.backend_name == "rapidocr"

def test_ocr_handler_init_invalid():
    with pytest.raises(Exception) as excinfo:
        OCRHandler(backend="invalid_backend")
    assert "Unsupported OCR backend" in str(excinfo.value)

def test_ocr_handler_run_success():
    """Test successful OCR run with mocked backend."""
    with patch("expense_manager.components.ocr_handler.ensure_local_artifact") as mock_ensure, \
         patch("expense_manager.components.ocr_handler.rapidocr_backend") as mock_backend:
        
        mock_ensure.return_value = "/tmp/local_img.jpg"
        # Mock backend return: [ [bbox, text, conf], ... ]
        mock_backend.return_value = [
            [[0,0,1,1], "Receipt Text", 0.99]
        ]
        
        ocr = OCRHandler(backend="rapidocr")
        result = ocr.run("gs://bucket/img.jpg")
        
        assert result.success is True
        assert "Receipt Text" in result.text
        assert result.backend == "rapidocr"

def test_ocr_handler_run_empty_text():
    """Test OCR run where backend returns empty list (no text)."""
    with patch("expense_manager.components.ocr_handler.ensure_local_artifact") as mock_ensure, \
         patch("expense_manager.components.ocr_handler.rapidocr_backend") as mock_backend:
        
        mock_ensure.return_value = "/tmp/local_img.jpg"
        mock_backend.return_value = []
        
        ocr = OCRHandler(backend="rapidocr")
        result = ocr.run("path/img.jpg")
        
        assert result.success is True
        assert result.text == ""

def test_ocr_handler_run_failure():
    """Test exception handling during OCR run."""
    with patch("expense_manager.components.ocr_handler.ensure_local_artifact") as mock_ensure:
        mock_ensure.side_effect = Exception("Download failed")
        
        ocr = OCRHandler(backend="rapidocr")
        result = ocr.run("path/img.jpg")
        
        assert result.success is False
        assert "Download failed" in result.error
