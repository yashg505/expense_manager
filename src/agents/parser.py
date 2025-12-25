from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json
import sys

from src.llm.openai_client import OpenAIClient
from src.logger import get_logger
from src.exception import CustomException


logger = get_logger(__name__)


# -----------------------------------------------------------
# Data Models
# -----------------------------------------------------------

@dataclass
class ReceiptHeader:
    date: Optional[str]
    time: Optional[str]
    shop: Optional[str]


@dataclass
class ParsedItem:
    item: str
    type: str
    item_count: int
    quantity_kg_l: Optional[float]
    final_price: float


@dataclass
class ParsedReceipt:
    header: ReceiptHeader
    items: List[ParsedItem]


# -----------------------------------------------------------
# Parser Agent
# -----------------------------------------------------------

class Parser:
    """
    LLM-based parser that extracts:
      - date, time, shop
      - per-item: item, type, item_count, quantity_kg_l, final_price
    from messy OCR text.
    """

    def __init__(self, llm: Optional[OpenAIClient] = None):
        self.llm = llm or OpenAIClient()
        logger.info("Parser initialized with LLM backend")

    # -------------------------------------------------------
    def parse(self, ocr_text: str) -> ParsedReceipt:
        """Main entry → return ParsedReceipt dataclass."""
        try:
            prompt = self._build_prompt(ocr_text)
            llm_output = self.llm.chat(prompt)

            logger.debug("LLM raw output: %s", llm_output)

            structured = self._validate_and_convert(llm_output)
            logger.info("Parser extracted %s items", len(structured["items"]))

            return self._to_dataclasses(structured)

        except Exception as e:
            logger.error("Parser failed: %s", e)
            raise CustomException(e, sys)

    # -------------------------------------------------------
    def _build_prompt(self, text: str) -> str:
        """Prompt that enforces strict JSON output."""
        return f"""
You are an expert receipt parsing assistant.

Extract structured data from the OCR text provided below.

OCR TEXT:
{text}

Your task:
1. Extract the *receipt-level* details:
   - date
   - time
   - shop

2. Extract each purchased item with:
   - item: product name
   - type: short descriptive type inferred from item name
   - item_count: integer (default 1 if not present)
   - quantity_kg_l: numeric value or null (weight/volume)
   - final_price: float

3. Ignore TOTAL, TAX, DISCOUNT, store footer, and extra text.

Return ONLY valid JSON in this exact format:

{
  "date": "DD.MM.YYYY",
  "time": "HH:MM:SS",
  "shop": "string",
  "items": [
    {
      "item": "Protein Bar",
      "type": "Protein Bar",
      "item_count": 2,
      "quantity_kg_l": 2,
      "final_price": 5.00
    }
  ]
}

No explanations. No comments. JSON only.
"""

    # -------------------------------------------------------
    def _validate_and_convert(self, output: str) -> Dict[str, Any]:
        """Ensure LLM output is valid JSON."""
        try:
            data = json.loads(output)
            return data

        except json.JSONDecodeError as je:
            logger.error("Parser: invalid JSON returned by LLM: %s", je)
            raise

    # -------------------------------------------------------
    def _to_dataclasses(self, data: Dict[str, Any]) -> ParsedReceipt:
        """Convert parsed JSON into strong dataclasses."""
        
        header = ReceiptHeader(
            date=data.get("date"),
            time=data.get("time"),
            shop=data.get("shop")
        )

        items = []
        for item in data.get("items", []):
            items.append(
                ParsedItem(
                    item=item.get("item", "").strip(),
                    type=item.get("type", "").strip(),
                    item_count=int(item.get("item_count", 1)),
                    quantity_kg_l=item.get("quantity_kg_l"),
                    final_price=float(item.get("final_price", 0.0)),
                )
            )

        return ParsedReceipt(
            header=header,
            items=items
        )
