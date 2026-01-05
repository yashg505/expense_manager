from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class ItemClassification(BaseModel):
    item_type: str
    taxonomy_id: str
    category: str
    sub_category_i: str
    sub_category_ii: str

class Price(BaseModel):
    amount: float = Field(..., description="Price amount before discount")
    discount: float = Field(..., description="discount amount")

class BaseParsedItem(BaseModel):
    item: str = Field(..., description="Item name, Title Case")
    item_type: str = Field(..., description="generic item type, e.g., apple, milk, etc. in singular form, title case")
    item_count: int = Field(..., description="Number of items purchased") 
    price: Price

class ParsedItem(BaseParsedItem):
    classification: Optional[ItemClassification] = None

class ParserLLMResponse(BaseModel):
    date: Optional[str] = Field(None, description="Receipt date in YYYY-MM-DD format")
    time: Optional[str] = Field(None, description="Receipt time in HH:MM:SS format")
    shop: Optional[str] = Field(None, description="Shop name")
    parsed_items: List[BaseParsedItem]
    model_config = ConfigDict(extra="forbid")

class ParserResponse(ParserLLMResponse):
    parsed_items: List[ParsedItem]
