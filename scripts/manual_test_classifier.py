from expense_manager.agents.classifier import ClassifierAgent
from expense_manager.logger import get_logger
from dotenv import load_dotenv
from expense_manager.llm.openai_client import OpenAIClient

load_dotenv()
logger = get_logger(__name__)

def test_classifier():
    # Initialize with None for LLM if you want to test pure vector first, 
    # or pass an OpenAIClient instance for full Step 5 testing.
    agent = ClassifierAgent(llm_client=OpenAIClient(model_name="gpt-4.1"))
    
    # Test cases: (item_name, shop_name, item_type)
    test_items = [
        ("Pink Lady Apples", "Tesco", "Apples"),
        ("Whole Milk", "Dunnes", "Dairy"),
        ("Gillette Mach 3", "Boots", "Razors"),
        ("Basmati Rice", "Tesco", "Rice"),
        ("Colgate Toothpaste", "SuperValu", "Toothpaste")
    ]
    
    print("\n--- Starting Classification Test ---\n")
    
    for name, shop, itype in test_items:
        result = agent.classify_item(name, shop_name=shop, item_type=itype)
        if result:
            print(f"Input: '{name}' | Shop: '{shop}' | Type: '{itype}'")
            print(f"  Result ID: {result.taxonomy_id}")
            print(f"  Category:  {result.category}")
            print(f"  Sub I:     {result.sub_category_i}")
            print(f"  Sub II:    {result.sub_category_ii}")
            print(f"  Score:     {result.score:.4f}")
            print("-" * 30)
        else:
            print(f"Item: {name} - No match found.")

if __name__ == "__main__":
    test_classifier()
