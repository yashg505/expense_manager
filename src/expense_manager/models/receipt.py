from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
from expense_manager.models.parsers import ParserResponse

class ReceiptImage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_id: str
    file_name: str
    image_path: str
    local_path: Optional[str] = None
    fingerprint: str

    ocr_text: Optional[str] = None
    parser_response: Optional[ParserResponse] = None

    processed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
