# ✅ Pre-Coding Finalization Checklist

This document outlines the items that must be finalized **before starting implementation** of the Receipt → Taxonomy Classification System.

---

## 1. Data & Schema Contracts
- [ ] Finalize all DB schemas:
  - **image_metadata**: `image_id (PK)`, `file_name`, `fingerprint (unique)`, `image_path`, `timestamp`
  - **main_data**: `id (PK)`, `image_id (FK)`, `item_text`, `taxonomy`, `qty`, `price`
  - **corrections**: `id (PK)`, `item_text`, `corrected_taxonomy`
  - **taxonomy**: loaded from `taxonomy.json` with IDs + hierarchy
- [ ] Confirm datamodels:
  - `ReceiptImage` (image_id, file_name, fingerprint, etc.)
  - `ParsedItem` (text, qty, price, taxonomy)

---

## 2. Pipelines & Flow Contracts
- [ ] Lock the end-to-end flow:
  *Upload → OCR → Parse → Classify → Save → Review → Correct → Sync → Report*
- [ ] Define checkpoints:
  - Duplicate check before OCR
  - Corrections DB check before FAISS/LLM
- [ ] Decide background re-embedding strategy:
  - Manual trigger vs scheduled job

---

## 3. LLM + FAISS Integration
- [ ] Choose embedding model (e.g., `text-embedding-3-small`).
- [ ] Decide parser strategy (regex fallback vs always LLM).
- [ ] Freeze prompt templates for parsing + classification.
- [ ] Lock FAISS index dimensions (must match embedding model).

---

## 4. Error Handling & Logging
- [ ] Define error handling policy (`exception.py`).
- [ ] Set logging granularity (per step, DB ops, FAISS queries).
- [ ] Retry policies for OCR/LLM failures.

---

## 5. User Interaction & Corrections
- [ ] Confirm UI logic:
  - Corrections update DB immediately?
  - Corrections trigger embeddings update immediately or batched?
- [ ] Confirm corrections always override history.

---

## 6. Configuration & Paths
- [ ] Finalize `config.py` with:
  - Paths for DBs, indexes, taxonomy
  - Dev vs Prod configs
- [ ] Define environment variable usage (API keys, Google creds)

---

## 7. Reporting & Dashboards
- [ ] Define analytics to show in dashboard (`page3_dashboard.py`).
- [ ] Confirm Google Sheets schema (columns + formatting).

---

## 8. Testing Strategy
- [ ] Define unit vs integration test coverage.
- [ ] Prepare seed test data (sample receipts, taxonomy).

---

### 📌 Summary
Before coding starts, **DB schemas, taxonomy format, FAISS/LLM choices, prompt templates, and correction logic** must be locked.  
This ensures all developers work against the same contracts and integration boundaries.
