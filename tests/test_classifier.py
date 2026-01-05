import pytest
from expense_manager.agents.classifier import ClassifierAgent
from expense_manager.models.classifier import ClassificationResult

@pytest.fixture(scope="module")
def classifier_agent():
    """
    Fixture to initialize the ClassifierAgent once for the test module.
    This avoids reloading the FAISS index and embedding model for every test.
    """
    return ClassifierAgent()

def test_classify_known_items(classifier_agent):
    """
    Test classification of items that should have clear matches in the taxonomy.
    """
    test_cases = [
        ("Pink Lady Apples", "Food Items1", "Fruits and Vegetables"),
        ("Whole Milk", "Food Items", "Dairy Products"),
        ("Gillette Mach 10", "Personal Care1", "Shaving and Hair Removal"),
        ("Basmati Rice", "Food Items", "Grains, Flours & Pulses"),
        ('Toothpaste", "Personal Care1", "Oral Care1"),')
    ]

    for item_name, expected_category, expected_sub_i in test_cases:
        result = classifier_agent.classify_item(item_name)
        
        assert result is not None, f"Failed to classify '{item_name}'"
        assert isinstance(result, ClassificationResult)
        assert result.category == expected_category, f"Expected category '{expected_category}' for '{item_name}', got '{result.category}'"
        
        if expected_sub_i:
            assert result.sub_category_i == expected_sub_i, f"Expected sub_category_i '{expected_sub_i}' for '{item_name}', got '{result.sub_category_i}'"

def test_classify_empty_input(classifier_agent):
    """Test that empty or None input returns None gracefully."""
    assert classifier_agent.classify_item("") is None
    assert classifier_agent.classify_item("   ") is None
    # If the type hint allows None, we could test None, but mypy might complain
    # assert classifier_agent.classify_item(None) is None

def test_classify_unknown_gibberish(classifier_agent):
    """
    Test input that is unlikely to match anything strongly.
    Note: Vector search ALWAYS returns a 'nearest' match, so this test 
    checks structure validity rather than 'None' return, unless we enforce a score threshold.
    """
    result = classifier_agent.classify_item("asdfghjkl12345")
    assert result is not None
    assert isinstance(result, ClassificationResult)
    # Ideally, we would assert result.score is high (distance) or low (similarity) depending on metric
