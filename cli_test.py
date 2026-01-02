import json
from dotenv import load_dotenv
from PIL import Image
from src.dbs.taxonomy_db import TaxonomyDB
from src.components.ocr_handler import OCRHandler
from src.llm.openai_client import OpenAIClient
from src.agents.parser import parse_receipt


load_dotenv()

def main():
    print("Hello from expense-manager!")

    # taxonomy = TaxonomyDB()
    # cats = taxonomy.get_row_by_id(1)
    # print(cats)
    
    image_path = "artifacts/images/17000186820251224442777.png"
    # image_path = "artifacts/images/dunnes.jpeg"

    # image = Image.open(image_path)
    ocr = OCRHandler(backend="rapidocr")
    ocr_result = ocr.run(image_path)

    if not ocr_result.success:
        print(f"OCR failed: {ocr_result.error}")
        return

    llm = OpenAIClient(model_name="gpt-4.1")
    result = parse_receipt(
        text=ocr_result.text,
        llm_client=llm,
    )

    json_dict = result.model_dump()
    print(json_dict)
    # print(json.dumps(json_dict, indent=2))

if __name__ == "__main__":
    main()
