from pydantic import BaseModel, Field
from typing import Optional

class ClassificationResult(BaseModel):
    category: str = Field(..., description="Primary category (e.g., Food Items)")
    sub_category_i: Optional[str] = Field(None, description="Secondary category")
    sub_category_ii: Optional[str] = Field(None, description="Tertiary category")
    score: float = Field(..., description="Similarity score from vector search")
    taxonomy_id: str = Field(..., description="The ID from the taxonomy database")
