import pytest
from unittest.mock import MagicMock
from expense_manager.agents.parser import parse_receipt
from expense_manager.models import ParserResponse, ParserLLMResponse, ParsedItem, BaseParsedItem, Price
from expense_manager.models.llm import LLMResponse

@pytest.fixture
def mock_llm_client():
    return MagicMock()

def test_parse_receipt_success(mock_llm_client):
    """
    Test successful parsing when LLM returns a valid ParserLLMResponse object.
    The function should convert it to ParserResponse.
    """
    ocr_text = "Tesco \n 2025-12-30 \n Milk 1.50"
    
    # Mock data returned by LLM (ParserLLMResponse)
    llm_output = ParserLLMResponse(
        date="2025-12-30",
        time='',
        shop="Tesco",
        parsed_items=[
            BaseParsedItem(
                item="Milk",
                item_type="Milk",
                item_count=1,
                price=Price(amount=1.50, discount=0.0)
            )
        ]
    )

    # Expected output from the function (ParserResponse)
    expected_response = ParserResponse(
        date="2025-12-30",
        time='',
        shop="Tesco",
        parsed_items=[
            ParsedItem(
                item="Milk",
                item_type="Milk",
                item_count=1,
                price=Price(amount=1.50, discount=0.0),
                classification=None # classification is None by default
            )
        ]
    )
    
    # Mock the generate call to return an LLMResponse containing the object
    mock_llm_client.generate.return_value = LLMResponse(
        content=llm_output,
        raw_response='{"mock": "json"}',
        model_name="gpt-4o-mini",
        provider="OpenAIClient"
    )
    
    result = parse_receipt(ocr_text, mock_llm_client)
    
    assert result == expected_response
    assert result.shop == "Tesco"
    assert len(result.parsed_items) == 1
    assert result.parsed_items[0].item == "Milk"
    assert isinstance(result.parsed_items[0], ParsedItem)

def test_parse_receipt_fallback_json(mock_llm_client):
    """
    Test fallback logic when LLM returns a JSON string instead of an object.
    """
    ocr_text = "Dunnes \n 2025-12-25 \n Bread 2.00"
    
    json_content = """
    {
        "date": "2025-12-25",
        "shop": "Dunnes",
        "parsed_items": [
            {
                "item": "Bread",
                "item_type": "Bread",
                "item_count": 1,
                "price": {"amount": 2.00, "discount": 0.0}
            }
        ]
    }
    """
    
    mock_llm_client.generate.return_value = LLMResponse(
        content=json_content,
        raw_response=json_content,
        model_name="gpt-4o-mini",
        provider="OpenAIClient"
    )
    
    result = parse_receipt(ocr_text, mock_llm_client)
    
    assert isinstance(result, ParserResponse)
    assert result.shop == "Dunnes"
    assert result.parsed_items[0].item == "Bread"

def test_parse_receipt_empty_text(mock_llm_client):
    """
    Test that providing empty OCR text raises a ValueError (wrapped in CustomException).
    """
    with pytest.raises(Exception) as excinfo:
        parse_receipt("", mock_llm_client)
    
    assert "Empty OCR text provided" in str(excinfo.value)

def test_parse_receipt_unexpected_type(mock_llm_client):
    """
    Test handling of unexpected return types from the LLM client.
    """
    mock_llm_client.generate.return_value = LLMResponse(
        content=123, # Unexpected integer
        raw_response="123",
        model_name="gpt-4o-mini",
        provider="OpenAIClient"
    )
    
    with pytest.raises(Exception) as excinfo:
        parse_receipt("some text", mock_llm_client)
    
    assert "Unexpected content type" in str(excinfo.value)
