# Neraium Demo - FastAPI + Next.js

## Run the Demo (active path)

```bash
python run_demo.py
```

This now launches:
- **FastAPI backend** at `http://localhost:8000`
- **Next.js frontend** at `http://localhost:3000`

The frontend is the primary demo UI. Gradio is no longer the active demo shell.

---

## Demo API endpoints

- `GET /api/demo/init`
- `GET /api/demo/frame/{index}`
- `GET /api/demo/summary`
- `POST /api/demo/reset`
- `GET /api/demo/stream`

All frames include phase, frame index, drift/health metrics, tetrahedral state, verdict, reasoning, and evidence.

---

## What changed

### Deprecated from active usage
- `ui.app:create_gradio_app` (legacy Gradio UI shell)
- Gradio launch path previously used by `run_demo.py`

### Still present for compatibility
- Legacy `ui/` Gradio-oriented component files still exist in-repo.
- They can be fully removed after callers/scripts depending on `ui.app` are retired.

---

## Manual run (optional)

Backend only:
```bash
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

Frontend only:
```bash
cd frontend
npm install
NEXT_PUBLIC_NERAIUM_API_BASE=http://localhost:8000 npm run dev
```
