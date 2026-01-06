from typing import Any, Dict, Optional
from pydantic import BaseModel

class LLMResponse(BaseModel):
    """
    Data Transfer Object (DTO) for standardized LLM outputs.
    Ensures that regardless of the provider, the application receives the same structure.
    """
    content: Any
    raw_response: str
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    provider: str
    metadata: Optional[Dict[str, Any]] = None
