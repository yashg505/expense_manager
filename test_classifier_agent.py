from src.agents.classifier import ClassifierAgent
from src.logger import get_logger

logger = get_logger(__name__)

def test_classifier():
    agent = ClassifierAgent()
    items = ["Pink Lady Apples", "Whole Milk", "Gillette Mach 3", "Basmati Rice", "Toothpaste"]
    
    for item in items:
        result = agent.classify_item(item)
        if result:
            print(f"Item: {item}")
            print(f"  Category: {result.category}")
            print(f"  Sub I:    {result.sub_category_i}")
            print(f"  Sub II:   {result.sub_category_ii}")
            print(f"  Score:    {result.score:.4f}")
            print("-" * 20)
        else:
            print(f"Item: {item} - No match found.")

if __name__ == "__main__":
    test_classifier()
