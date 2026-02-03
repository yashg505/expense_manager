## Structure of the code
User Question
     ↓
Schema-Aware Prompt
     ↓
LLM generates SQL ONLY
     ↓
Python executes SQL
     ↓
LLM summarizes ONLY returned rows

## Pre-requisite 
pip install streamlit requests

## Structure
src/expense_manager/components/ai_chabot/
  engine.py        <-- new (core shared logic)
  app.py           <-- thin FastAPI wrapper
  chat_ui.py       <-- Streamlit UI uses engine directly (or via API if you want)
  .env



Love this direction — your layout idea is super clear, and yes, we can absolutely move off Streamlit for this.

If you want less manual effort on receipt upload/cropping, I’d recommend:

Frontend: Next.js (React) + Tailwind
Backend: your current Python logic behind FastAPI
Receipt capture/scanning: camera upload in browser (getUserMedia) + auto-crop/cleanup in backend (OpenCV/Pillow), so users don’t manually crop first.
How to map your UI

Left panel: Receipt scanner (camera + drag/drop image + preview + “Scan”)
Center panel: Chatbot conversation + quick actions
Right panel: Total spend, category breakdown, trends/charts
Make it responsive so on mobile it becomes tab-based (Scan / Chat / Insights), similar to your mock.
Why this beats Streamlit for your case

Better file upload/camera handling
Fine-grained UI control (exactly like your mock)
Cleaner async flow for scan → OCR → categorize → update chat + totals
Implementation flow

Build FastAPI endpoints: /scan-receipt, /chat, /summary.
Keep your existing engine logic in Python (reuse from engine.py).
Build Next.js UI with a 3-column desktop layout.
Add auto-crop + perspective correction server-side before OCR.
Return parsed fields + confidence, then allow quick user edits in UI.
If you want, I can give you a starter folder structure + first-pass code for FastAPI + Next.js that plugs into your current ai_chabot engine directly.