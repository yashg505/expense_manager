# Deploy (Render + Vercel)

This repo is deployed as **two services**:

- **Backend API (FastAPI)** on Render
- **Frontend UI (Next.js)** on Vercel

This keeps secrets (OpenAI key, DB connection) on the backend only.

---

## 1) Backend: Render (FastAPI)

### Render settings

- **Root Directory**: repo root
- **Runtime**: Python
- **Build Command**:
  - `pip install .`
- **Start Command**:
  - `uvicorn expense_manager.components.ai_chabot.app:app --host 0.0.0.0 --port $PORT --app-dir src`

### Required environment variables (Render)

- `OPENAI_API_KEY` = your OpenAI API key
- `NEON_CONN_STR` = your Neon Postgres connection string
- `CORS_ALLOW_ORIGINS` = your Vercel URL(s), comma-separated
  - Example: `https://expense-manager-frontend.vercel.app`
- `DEMO_KEY` = a shared demo key (protects public endpoints)
  - The API requires header `X-DEMO-KEY: <DEMO_KEY>` for:
    - `POST /chat`
    - `POST /scan-receipt`
    - `POST /receipts/{file_id}/confirm`

### Optional (recommended for public demos)

- `DISABLE_GSHEETS=1`
  - Skips Google Sheets export on confirm.
  - You can enable export later once you configure Google credentials on Render.

### Backend verification

After deploy, verify:

- `GET /health` returns `{ "ok": true }`
- `GET /docs` loads the Swagger UI

---

## 2) Frontend: Vercel (Next.js)

### Vercel settings

- **Root Directory**: `frontend`

### Environment variables (Vercel)

- `NEXT_PUBLIC_API_BASE_URL` = your Render backend URL
  - Example: `https://expense-manager-api.onrender.com`
- `NEXT_PUBLIC_DEMO_KEY` = must match the Render `DEMO_KEY`

### Frontend verification

Open the Vercel URL and confirm:

- API badge shows **connected**
- Upload + Scan works
- Confirm & Save triggers confetti and returns `exported: false` if `DISABLE_GSHEETS=1`

---

## Notes

- Do **not** commit `.env` files with real keys. Rotate keys if they were exposed.
- For production, restrict `CORS_ALLOW_ORIGINS` to your real UI domain(s).

