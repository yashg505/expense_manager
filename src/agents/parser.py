import json
import sys

from src.logger import get_logger
from src.exception import CustomException
from src.models import ParserResponse

logger = get_logger(__name__)

# -----------------------------------------------------------
# Parser Agent
# -----------------------------------------------------------
PARSER_PROMPT = """
You are an expert at extracting structured data from receipts. Given the OCR text from a receipt, extract the relevant information.
Take care of item type field as there are different names for Apples like Pink Lady Kids Apples,
or Fairtrade Org. Yellow Bananas for Banana. Take care of the shop name as well, don't include the address or other details.
Don't mess up the dates.
Extract the merchant name. If the name is generic (like 'Supermarket'), look for brand names in the items
or loyalty program names to determine the specific store brand.

Receipt OCR Extracted text: 
{text}
"""

def parse_receipt(
    text: str,
    llm_client,
) -> ParserResponse:
    """
    Parse raw OCR receipt text into structured data using the LLM client's 
    built-in validation logic.
    """
    logger.info("Initiating receipt parsing logic.")

    try:
        if not text or not text.strip():
            logger.error("Attempted to parse empty OCR text.")
            raise ValueError("Empty OCR text provided")

        prompt = PARSER_PROMPT.format(text=text)

        # This utilizes the verbose logic we built into BaseLLM.
        response = llm_client.generate(
            prompt=prompt,
            response_model=ParserResponse 
        )

        logger.debug(f"LLM Response received. Provider: {response.provider}")

        if isinstance(response.content, ParserResponse):
            logger.info("Successfully parsed receipt into ParserResponse object.")
            return response.content
        
        if isinstance(response.content, str):
            logger.warning("LLM returned string instead of object. Attempting manual parse.")
            parsed_data = json.loads(response.content)
            return ParserResponse.model_validate(parsed_data)

        raise ValueError(f"Unexpected content type: {type(response.content)}")

    except Exception as exc:
        logger.error(f"Receipt parsing failed: {str(exc)}", exc_info=True)
        raise CustomException(exc, sys)