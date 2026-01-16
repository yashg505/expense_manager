import pytest
from unittest.mock import MagicMock, patch
from expense_manager.models import OCRResult, ParserResponse, ParsedItem, Price, ClassificationResult
from expense_manager.components.ocr_handler import OCRHandler
from expense_manager.agents import parser
from expense_manager.agents.classifier import ClassifierAgent

# We'll mock the internal methods/dependencies, but test the flow control if possible.
# Since there isn't a single "Pipeline" class, we'll write a test that acts as the pipeline controller.

@pytest.fixture
def mock_pipeline_components():
    with patch("expense_manager.components.ocr_handler.OCRHandler") as MockOCR, \
         patch("expense_manager.agents.parser.parse_receipt") as mock_parse, \
         patch("expense_manager.agents.classifier.ClassifierAgent") as MockClassifier:
        
        # OCR Mock
        mock_ocr_instance = MockOCR.return_value
        mock_ocr_instance.run.return_value = OCRResult(
            text="Tesco\nMilk 1.50",
            raw_data=None,
            success=True,
            backend="mock"
        )
        
        # Parser Mock
        mock_parse.return_value = ParserResponse(
            shop="Tesco",
            date="2025-01-01",
            time=None,
            parsed_items=[
                ParsedItem(
                    item="Milk",
                    item_type="Dairy",
                    item_count=1,
                    price=Price(amount=1.50, discount=0.0),
                    classification=None
                )
            ]
        )
        
        # Classifier Mock
        mock_classifier_instance = MockClassifier.return_value
        mock_classifier_instance.classify_item.return_value = ClassificationResult(
            category="Food",
            sub_category_i="Dairy",
            taxonomy_id="123",
            score=0.99
        )
        
        yield {
            "ocr": mock_ocr_instance,
            "parse": mock_parse,
            "classifier": mock_classifier_instance
        }

def test_end_to_end_pipeline_simulation(mock_pipeline_components):
    """
    Simulates the data flow from Image -> OCR -> Parser -> Classifier.
    """
    # 1. Initialize components
    ocr = mock_pipeline_components["ocr"] # In reality: OCRHandler()
    classifier = mock_pipeline_components["classifier"] # In reality: ClassifierAgent()
    llm_client = MagicMock() # Mock LLM client

    # 2. Run OCR
    image_path = "dummy.jpg"
    ocr_result = ocr.run(image_path)
    assert ocr_result.success
    assert ocr_result.text == "Tesco\nMilk 1.50"

    # 3. Parse Receipt
    # parse_receipt(text, llm_client)
    parsed_data = parser.parse_receipt(ocr_result.text, llm_client)
    assert parsed_data.shop == "Tesco"
    assert len(parsed_data.parsed_items) == 1

    # 4. Classify Items
    final_items = []
    for item in parsed_data.parsed_items:
        classification = classifier.classify_item(item.item, shop_name=parsed_data.shop, item_type=item.item_type)
        
        # Merge logic (usually done in the UI/Controller)
        final_item = {
            "item": item.item,
            "taxonomy_id": classification.taxonomy_id,
            "category": classification.category,
            "price": item.price.amount
        }
        final_items.append(final_item)

    # 5. Verify results
    assert len(final_items) == 1
    assert final_items[0]["taxonomy_id"] == "123"
    assert final_items[0]["category"] == "Food"
    
    # Verify calls
    ocr.run.assert_called_with(image_path)
    mock_pipeline_components["parse"].assert_called() # parse_receipt
    classifier.classify_item.assert_called_with("Milk", shop_name="Tesco", item_type="Dairy")
