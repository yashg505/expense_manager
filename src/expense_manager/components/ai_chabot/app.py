# # from fastapi import FastAPI
# # from pydantic import BaseModel
# # from typing import Optional

# # from expense_manager.components.ai_chabot.engine import answer

# # app = FastAPI(title="Expense DB Chatbot API")

# # class ChatRequest(BaseModel):
# #     message: str
# #     conversation_id: Optional[str] = None

# # @app.post("/chat")
# # def chat(req: ChatRequest):
# #     return answer(req.message, req.conversation_id)

# # src/expense_manager/components/ai_chabot/app.py
# from typing import Optional
# import os
# import tempfile

# import uuid
# from PIL import Image

# from expense_manager.utils.image_fingerprint import get_image_fingerprint
# from expense_manager.utils.artifacts_gcs import upload_artifact
# from expense_manager.dbs.image_metadata import ImageMetadataDB
# from expense_manager.dbs.taxonomy_db import TaxonomyDB
# from expense_manager.dbs.corrections_db import CorrectionsDB
# from expense_manager.dbs.main_db import MainDB
# from expense_manager.agents.classifier import ClassifierAgent
# from expense_manager.integration.gsheet_handler import GSheetHandler
# import pandas as pd


# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel

# from expense_manager.components.ai_chabot.engine import answer
# from expense_manager.components.ocr_handler import OCRHandler
# from expense_manager.agents.parser import parse_receipt
# from expense_manager.llm.openai_client import OpenAIClient
# from expense_manager.utils.load_config import load_config_file

# app = FastAPI(title="Expense Manager API")
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# class DraftItem(BaseModel):
#     item_text: str
#     item_type: Optional[str] = None
#     quantity: int = 1
#     price: float = 0.0
#     discount: float = 0.0
#     predicted_taxonomy_id: Optional[str] = None
#     taxonomy_id: Optional[str] = None  # user final choice

# class ConfirmReceiptRequest(BaseModel):
#     shop: Optional[str] = None
#     date: Optional[str] = None
#     time: Optional[str] = None
#     items: list[DraftItem]

# @app.post("/scan-receipt")
# async def scan_receipt(file: UploadFile = File(...)):
#     if not file.content_type or not file.content_type.startswith("image/"):
#         raise HTTPException(status_code=400, detail="Upload an image file")

#     data = await file.read()
#     if not data:
#         raise HTTPException(status_code=400, detail="Empty upload")

#     # 1) Fingerprint + dedupe (like Streamlit uploader)
#     try:
#         pil_img = Image.open(io.BytesIO(data)).convert("RGB")
#         fingerprint = get_image_fingerprint(pil_img)
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

#     meta_db = ImageMetadataDB()
#     existing = meta_db.get_by_fingerprint(fingerprint)
#     if existing and existing.get("status") == "uploaded":
#         raise HTTPException(status_code=409, detail="Duplicate receipt (already uploaded)")

#     # 2) Create/Reuse file_id
#     file_id = existing["file_id"] if existing else uuid.uuid4().hex
#     suffix = os.path.splitext(file.filename or "receipt.jpg")[1] or ".jpg"
#     file_name = file.filename or f"{file_id}{suffix}"

#     # 3) Upload image bytes to GCS (so we keep the artifact)
#     image_path = upload_artifact(data, f"{file_id}{suffix}", content_type=file.content_type)

#     # 4) OCR using a temp file
#     with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
#         tmp.write(data)
#         temp_path = tmp.name

#     try:
#         ocr = OCRHandler(backend="rapidocr")
#         ocr_result = ocr.run(temp_path)
#     finally:
#         try:
#             os.unlink(temp_path)
#         except Exception:
#             pass

#     if not ocr_result.success:
#         raise HTTPException(status_code=500, detail=ocr_result.error or "OCR failed")

#     # 5) Parse receipt text
#     config = load_config_file()
#     llm = OpenAIClient(model_name=config["llm"]["classification_model"])
#     parsed = parse_receipt(ocr_result.text, llm)

#     # 6) Pre-classify items so UI has “predicted category”
#     classifier = ClassifierAgent(llm_client=llm)
#     txdb = TaxonomyDB()

#     draft_items: list[dict] = []
#     for it in parsed.parsed_items:
#         c = classifier.classify_item(
#             item_name=it.item,
#             shop_name=parsed.shop or "Unknown",
#             item_type=it.item_type or "Unknown",
#         )

#         predicted_id = str(c.taxonomy_id)
#         draft_items.append({
#             "item_text": it.item,
#             "item_type": it.item_type,
#             "quantity": it.item_count,
#             "price": float(it.price.amount),
#             "discount": float(it.price.discount),
#             "predicted_taxonomy_id": predicted_id,
#             "taxonomy_id": predicted_id,  # default final = predicted
#             "predicted_full_path": (txdb.get_row_by_id(predicted_id) or {}).get("full_path"),
#         })

#     # 7) Persist draft state to image_metadata.json_state
#     state_dict = {
#         "file_id": file_id,
#         "file_name": file_name,
#         "image_path": image_path,
#         "fingerprint": fingerprint,
#         "ocr_text": ocr_result.text,
#         "parsed": {
#             "shop": parsed.shop,
#             "date": parsed.date,
#             "time": parsed.time,
#             "items": draft_items,
#         },
#     }
#     meta_db.upsert_image(
#         file_id=file_id,
#         file_name=file_name,
#         fingerprint=fingerprint,
#         image_path=image_path,
#         state_dict=state_dict,
#     )
#     # optional: meta_db.update_status(file_id, "pending_review")

#     return {"file_id": file_id, **state_dict["parsed"]}

# @app.get("/taxonomy")
# def taxonomy():
#     txdb = TaxonomyDB()
#     rows = txdb.get_all_rows()
#     rows = sorted(rows, key=lambda r: (r.get("full_path") or ""))
#     return [{"id": str(r["id"]), "full_path": r.get("full_path")} for r in rows]

# @app.post("/receipts/{file_id}/confirm")
# def confirm_receipt(file_id: str, req: ConfirmReceiptRequest):
#     meta_db = ImageMetadataDB()
#     main_db = MainDB()
#     corr_db = CorrectionsDB()
#     txdb = TaxonomyDB()

#     # Save corrections + build MainDB payload
#     shop = req.shop or "Unknown"

#     new_items = []
#     for it in req.items:
#         final_tax = (it.taxonomy_id or "UNCATEGORIZED").strip()
#         predicted_tax = (it.predicted_taxonomy_id or "UNCATEGORIZED").strip()

#         if final_tax != predicted_tax and final_tax != "UNCATEGORIZED":
#             corr_db.add_correction(
#                 shop_name=shop,
#                 item_text=it.item_text,
#                 taxonomy_id=final_tax,
#                 corrected_item_type=it.item_type,
#             )

#         new_items.append({
#             "item": it.item_text,
#             "taxonomy_id": final_tax,
#             "item_count": int(it.quantity or 1),
#             "price": float(it.price or 0.0),
#             "discount": float(it.discount or 0.0),
#             "item_type": it.item_type,
#         })

#     # 1) Write to processed_items
#     main_db.insert_finalized_items(
#         file_id=file_id,
#         shop_name=shop,
#         receipt_date=req.date or "",
#         receipt_time=req.time or "",
#         items=new_items,
#     )

#     # 2) Export to Google Sheets (same shape as your Streamlit export)
#     sheet_type = load_config_file()["sheets"].get("expense_sheet_type", "expense")
#     handler = GSheetHandler(sheet_type=sheet_type)

#     tax_map = {str(r["id"]): r for r in txdb.get_all_rows()}
#     export_rows = []
#     for row in main_db.get_items_by_file_id(file_id):
#         tax = tax_map.get(str(row["taxonomy_id"]), {})
#         export_rows.append({
#             "Date": row.get("receipt_date"),
#             "Time": row.get("receipt_time"),
#             "Shop": row.get("shop_name"),
#             "Item": row.get("item_text"),
#             "Type": row.get("item_type"),
#             "Category": tax.get("category", "Uncategorized"),
#             "Sub Category I": tax.get("sub_category_i", ""),
#             "Sub Category II": tax.get("sub_category_ii", ""),
#             "Quantity": row.get("quantity"),
#             "Price": row.get("price"),
#             "Discount": row.get("discount", 0),
#             "Total": row.get("total"),
#         })

#     df = pd.DataFrame(export_rows)
#     handler.append_df_to_sheet(df)

#     # 3) Mark uploaded (locks edits in ImageMetadataDB)
#     meta_db.update_status(file_id, "uploaded")

#     return {"ok": True, "exported": True, "file_id": file_id}


# class ChatRequest(BaseModel):
#     message: str
#     conversation_id: Optional[str] = None

# @app.get("/health")
# def health():
#     return {"ok": True}

# @app.post("/chat")
# def chat(req: ChatRequest):
#     return answer(req.message, req.conversation_id)

# @app.post("/scan-receipt")
# async def scan_receipt(file: UploadFile = File(...)):
#     if not file.content_type or not file.content_type.startswith("image/"):
#         raise HTTPException(status_code=400, detail="Upload an image file")

#     data = await file.read()
#     suffix = os.path.splitext(file.filename or "receipt.jpg")[1] or ".jpg"

#     with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
#         tmp.write(data)
#         temp_path = tmp.name

#     ocr = OCRHandler(backend="rapidocr")
#     ocr_result = ocr.run(temp_path)
#     if not ocr_result.success:
#         raise HTTPException(status_code=500, detail=ocr_result.error or "OCR failed")

#     config = load_config_file()
#     llm = OpenAIClient(model_name=config["llm"]["classification_model"])
#     parsed = parse_receipt(ocr_result.text, llm)

#     return {
#         "shop": parsed.shop,
#         "date": parsed.date,
#         "time": parsed.time,
#         "items": [i.model_dump() for i in parsed.parsed_items],
#         "ocr_text": ocr_result.text,
#     }

from __future__ import annotations

import io
import os
import tempfile
import uuid
from typing import Optional

from PIL import Image
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from expense_manager.components.ai_chabot.engine import answer
from expense_manager.components.ocr_handler import OCRHandler
from expense_manager.agents.parser import parse_receipt
from expense_manager.llm.openai_client import OpenAIClient
from expense_manager.utils.load_config import load_config_file
from expense_manager.utils.image_fingerprint import get_image_fingerprint

from expense_manager.dbs.image_metadata import ImageMetadataDB
from expense_manager.dbs.taxonomy_db import TaxonomyDB
from expense_manager.dbs.corrections_db import CorrectionsDB
from expense_manager.dbs.main_db import MainDB
from expense_manager.integration.gsheet_handler import GSheetHandler


def _parse_cors_origins(raw: Optional[str]) -> list[str]:
    """
    Render/Vercel deploys often need tight CORS (single UI origin).
    For local dev, default to localhost origins.
    """
    if not raw:
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


_DEMO_KEY = os.getenv("DEMO_KEY")  # If set, protect write/LLM endpoints.


def require_demo_key(x_demo_key: Optional[str] = Header(default=None, alias="X-DEMO-KEY")) -> None:
    """
    Lightweight protection for public demos. If DEMO_KEY is configured,
    requests must send header `X-DEMO-KEY: <value>`.
    """
    if not _DEMO_KEY:
        return
    if not x_demo_key or x_demo_key != _DEMO_KEY:
        raise HTTPException(status_code=401, detail="Missing/invalid demo key")


app = FastAPI(title="Expense Manager API")

CORS_ALLOW_ORIGINS = _parse_cors_origins(os.getenv("CORS_ALLOW_ORIGINS"))
CORS_ALLOW_ORIGIN_REGEX = os.getenv("CORS_ALLOW_ORIGIN_REGEX") or None
app.add_middleware(
    CORSMiddleware,
    # For production: set env CORS_ALLOW_ORIGINS to your Vercel URL(s),
    # e.g. "https://expense-manager-xyz.vercel.app,https://www.yourdomain.com"
    allow_origins=CORS_ALLOW_ORIGINS,
    # If you also need to allow preview subdomains (e.g. Cloudflare Pages commit URLs),
    # set CORS_ALLOW_ORIGIN_REGEX to a regex like:
    #   ^https://([a-z0-9-]+\\.)?expense-manager-7ma\\.pages\\.dev$
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class DraftItem(BaseModel):
    item_text: str
    item_type: Optional[str] = None
    quantity: int = 1
    price: float = 0.0
    discount: float = 0.0
    predicted_taxonomy_id: Optional[str] = None
    taxonomy_id: Optional[str] = None  # user-final selection


class ConfirmReceiptRequest(BaseModel):
    shop: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    items: list[DraftItem]


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat")
def chat(req: ChatRequest, _: None = Depends(require_demo_key)):
    return answer(req.message, req.conversation_id)


@app.get("/taxonomy")
def taxonomy():
    txdb = TaxonomyDB()
    rows = txdb.get_all_rows()
    rows = sorted(rows, key=lambda r: (r.get("full_path") or ""))
    return [{"id": str(r["id"]), "full_path": r.get("full_path")} for r in rows]


@app.post("/scan-receipt")
async def scan_receipt(file: UploadFile = File(...), _: None = Depends(require_demo_key)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")

    # Fingerprint for dedupe
    try:
        pil_img = Image.open(io.BytesIO(data)).convert("RGB")
        fingerprint = get_image_fingerprint(pil_img)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    meta_db = ImageMetadataDB()
    existing = meta_db.get_by_fingerprint(fingerprint)
    if existing and existing.get("status") == "uploaded":
        raise HTTPException(status_code=409, detail="Duplicate receipt (already uploaded)")

    file_id = existing["file_id"] if existing else uuid.uuid4().hex
    suffix = os.path.splitext(file.filename or "receipt.jpg")[1] or ".jpg"
    file_name = file.filename or f"{file_id}{suffix}"

    # OCR needs a local temp path
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        temp_path = tmp.name

    try:
        ocr = OCRHandler(backend="rapidocr")
        ocr_result = ocr.run(temp_path)
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass

    if not ocr_result.success:
        raise HTTPException(status_code=500, detail=ocr_result.error or "OCR failed")

    config = load_config_file()
    llm = OpenAIClient(model_name=config["llm"]["classification_model"])

    parsed = parse_receipt(ocr_result.text, llm)

    # Optional: classify items (can be memory-heavy in small containers due to torch/sentence-transformers).
    disable_classifier = os.getenv("DISABLE_CLASSIFIER", "").strip().lower() in {"1", "true", "yes"}
    classifier = None
    txdb = TaxonomyDB()
    if not disable_classifier:
        # Lazy import to keep the API boot lightweight on small instances (Render free tier).
        from expense_manager.agents.classifier import ClassifierAgent  # noqa: WPS433
        classifier = ClassifierAgent(llm_client=llm)

    draft_items: list[dict] = []
    for it in parsed.parsed_items:
        predicted_id = "UNCATEGORIZED"
        if classifier is not None:
            c = classifier.classify_item(
                item_name=it.item,
                shop_name=parsed.shop or "Unknown",
                item_type=it.item_type or "Unknown",
            )
            predicted_id = str(c.taxonomy_id)

        tx_row = txdb.get_row_by_id(predicted_id) if predicted_id and predicted_id != "UNCATEGORIZED" else None
        draft_items.append(
            {
                "item_text": it.item,
                "item_type": it.item_type,
                "quantity": int(it.item_count or 1),
                "price": float(it.price.amount),
                "discount": float(it.price.discount),
                "predicted_taxonomy_id": predicted_id,
                "taxonomy_id": predicted_id,  # default = predicted
                "predicted_full_path": (tx_row or {}).get("full_path"),
            }
        )

    # Persist draft state so we can track status + debugging in DB (image_metadata table)
    state_dict = {
        "file_id": file_id,
        "file_name": file_name,
        "fingerprint": fingerprint,
        # We store the raw OCR and parsed draft. (image_path can be added later if you want GCS/local artifact storage.)
        "ocr_text": ocr_result.text,
        "parsed": {
            "shop": parsed.shop,
            "date": parsed.date,
            "time": parsed.time,
            "items": draft_items,
        },
    }

    meta_db.upsert_image(
        file_id=file_id,
        file_name=file_name,
        fingerprint=fingerprint,
        image_path="",  # optional; keep blank for now
        state_dict=state_dict,
    )
    # meta_db.update_status(file_id, "pending_review")  # optional explicit status

    return {"file_id": file_id, **state_dict["parsed"]}


@app.post("/receipts/{file_id}/confirm")
def confirm_receipt(file_id: str, req: ConfirmReceiptRequest, _: None = Depends(require_demo_key)):
    main_db = MainDB()
    corr_db = CorrectionsDB()
    txdb = TaxonomyDB()
    meta_db = ImageMetadataDB()

    shop = req.shop or "Unknown"

    # Build payload for MainDB and save corrections (if user changed predicted -> final)
    new_items = []
    for it in req.items:
        final_tax = (it.taxonomy_id or "UNCATEGORIZED").strip()
        predicted_tax = (it.predicted_taxonomy_id or "UNCATEGORIZED").strip()

        if final_tax != predicted_tax and final_tax != "UNCATEGORIZED":
            corr_db.add_correction(
                shop_name=shop,
                item_text=it.item_text,
                taxonomy_id=final_tax,
                corrected_item_type=it.item_type,
            )

        new_items.append(
            {
                "item": it.item_text,
                "taxonomy_id": final_tax,
                "item_count": int(it.quantity or 1),
                "price": float(it.price or 0.0),
                "discount": float(it.discount or 0.0),
                "item_type": it.item_type,
            }
        )

    # 1) Save to DB
    main_db.insert_finalized_items(
        file_id=file_id,
        shop_name=shop,
        receipt_date=req.date or "",
        receipt_time=req.time or "",
        items=new_items,
    )

    exported = False
    disable_gsheets = os.getenv("DISABLE_GSHEETS", "").strip().lower() in {"1", "true", "yes"}
    if not disable_gsheets:
        import pandas as pd  # Lazy import to keep baseline memory lower
        # 2) Export to Google Sheet (same mapping style as Streamlit page2_review.py)
        sheet_type = load_config_file()["sheets"].get("expense_sheet_type", "expense")
        handler = GSheetHandler(sheet_type=sheet_type)

        tax_map = {str(r["id"]): r for r in txdb.get_all_rows()}
        export_rows = []
        for it in new_items:
            tax = tax_map.get(str(it["taxonomy_id"]), {}) if it["taxonomy_id"] else {}
            qty = int(it.get("item_count") or 1)
            price = float(it.get("price") or 0.0)
            discount = float(it.get("discount") or 0.0)
            total = price - discount

            export_rows.append(
                {
                    "Date": req.date,
                    "Time": req.time,
                    "Shop": shop,
                    "Item": it["item"],
                    "Type": it.get("item_type"),
                    "Category": tax.get("category", "Uncategorized"),
                    "Sub Category I": tax.get("sub_category_i", ""),
                    "Sub Category II": tax.get("sub_category_ii", ""),
                    "Quantity": qty,
                    "Price": price,
                    "Discount": discount,
                    "Total": total,
                }
            )

        df = pd.DataFrame(export_rows)
        handler.append_df_to_sheet(df)
        exported = True

    # 3) Mark uploaded (locks the draft)
    meta_db.update_status(file_id, "uploaded")

    return {"ok": True, "exported": exported, "file_id": file_id}
