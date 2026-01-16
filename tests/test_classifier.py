import pytest
from unittest.mock import MagicMock, patch
from expense_manager.agents.classifier import ClassifierAgent
from expense_manager.models.classifier import ClassificationResult

@pytest.fixture
def mock_dbs():
    with patch("expense_manager.agents.classifier.TaxonomyDB") as MockTaxonomy, \
         patch("expense_manager.agents.classifier.CorrectionsDB") as MockCorrections, \
         patch("expense_manager.agents.classifier.MainDB") as MockMain, \
         patch("expense_manager.agents.classifier.embed_texts") as mock_embed:
        
        # Setup common mock behaviors
        mock_taxonomy_instance = MockTaxonomy.return_value
        mock_corrections_instance = MockCorrections.return_value
        mock_main_instance = MockMain.return_value
        
        # Default behavior: no correction, no history match
        mock_corrections_instance.get_correction.return_value = None
        mock_main_instance.get_historical_exact_match.return_value = None
        mock_main_instance.get_historical_exact_match_type.return_value = None
        
        # Default behavior: mock embedding
        mock_embed.return_value = MagicMock()
        mock_embed.return_value.tolist.return_value = [0.1, 0.2, 0.3]
        
        yield {
            "taxonomy": mock_taxonomy_instance,
            "corrections": mock_corrections_instance,
            "main": mock_main_instance,
            "embed": mock_embed
        }

@pytest.fixture
def classifier_agent(mock_dbs):
    """
    Fixture to initialize the ClassifierAgent with mocked DBs.
    """
    return ClassifierAgent()

def test_classify_known_items(classifier_agent, mock_dbs):
    """
    Test classification where we mock the DBs to return specific results 
    mimicking a 'known item' scenario (e.g. via vector search).
    """
    # Setup mock to return a candidate for vector search
    mock_dbs["taxonomy"].search_vector.return_value = [
        {"row_id": "FOOD_FRUIT", "score": 0.1}
    ]
    mock_dbs["taxonomy"].get_row_by_id.side_effect = lambda x: {
        "category": "Food Items", 
        "sub_category_i": "Fruits",
        "sub_category_ii": None,
        "id": x
    }

    test_cases = [
        ("Pink Lady Apples", "Food Items", "Fruits"),
    ]

    for item_name, expected_category, expected_sub_i in test_cases:
        result = classifier_agent.classify_item(item_name)
        
        assert result is not None, f"Failed to classify '{item_name}'"
        assert isinstance(result, ClassificationResult)
        assert result.taxonomy_id != "UNCATEGORIZED"
        assert result.category == expected_category

def test_classify_empty_input(classifier_agent):
    """Test that empty or None input returns Uncategorized result gracefully."""
    res1 = classifier_agent.classify_item("")
    assert res1.taxonomy_id == "UNCATEGORIZED"
    
    res2 = classifier_agent.classify_item("   ")
    assert res2.taxonomy_id == "UNCATEGORIZED"

def test_classify_unknown_gibberish(classifier_agent, mock_dbs):
    """
    Test input that returns no candidates.
    """
    mock_dbs["taxonomy"].search_vector.return_value = []
    
    result = classifier_agent.classify_item("asdfghjkl12345")
    assert result is not None
    assert isinstance(result, ClassificationResult)
    assert result.taxonomy_id == "UNCATEGORIZED"

def test_classify_correction_hit(classifier_agent, mock_dbs):
    """Test that corrections DB hit returns immediately."""
    mock_dbs["corrections"].get_correction.return_value = ("CORRECTED_ID", "Corrected Type")
    mock_dbs["taxonomy"].get_row_by_id.return_value = {"category": "Corrected", "id": "CORRECTED_ID"}
    
    result = classifier_agent.classify_item("Wrong Item", shop_name="MyShop")
    
    assert result.taxonomy_id == "CORRECTED_ID"
    mock_dbs["corrections"].get_correction.assert_called_with("MyShop", "Wrong Item")
