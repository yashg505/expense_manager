#!/usr/bin/env bash
set -euo pipefail

echo "[render-start] python=$(python --version 2>&1)"
echo "[render-start] port=${PORT:-<missing>}"

python -c "import uvicorn; print('[render-start] uvicorn=' + uvicorn.__version__)"

exec python -m uvicorn expense_manager.components.ai_chabot.app:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --app-dir src \
  --log-level debug

