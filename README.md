# AI Sales & Booking Assistant (FastAPI)

Minimal dev README for local run.

Prerequisites

- Python 3.11+
- Docker (optional) for Qdrant/Ollama

Quick start (Windows PowerShell)

1. Copy `.env.example` to `.env` and edit values if needed:

```powershell
cd ai-sales-booking-fastapi
cp .env.example .env
```

2. Create venv and install dependencies (already automated in repo):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Start the API using the helper script (uses `API_PORT` from `.env`, default 8010):

```powershell
.\start.ps1
```

Or manually:

```powershell
# activate venv first
.\venv\Scripts\Activate.ps1
# run uvicorn on port (example 8010)
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8010
```

API endpoints

- POST `/api/v1/ai/reply` — body: `{ "tenant_id": "<uuid>", "message": "..." }`
- Booking endpoints: `/api/v1/appointments` etc.

Notes

- Ensure Ollama and Qdrant are running and reachable by the URLs in `.env`.
- The service enforces tenant isolation when querying Qdrant using `metadata.tenant_id`.

AI providers (Ollama, Qdrant Embeddings, Groq)

- Chat provider is configurable with `LLM_PROVIDER`:
  - `ollama` (default): uses `OLLAMA_CHAT_MODEL` / `OLLAMA_MODEL`
  - `groq`: uses `GROQ_API_KEY` + `GROQ_MODEL`
- Embeddings provider is configurable with `EMBEDDING_PROVIDER`:
  - `qdrant` (default): uses Qdrant Inference with `QDRANT_EMBEDDING_MODEL`
  - `ollama`: uses `OLLAMA_EMBED_MODEL` / `OLLAMA_EMBEDDING_MODEL`
- If `EMBEDDING_PROVIDER=qdrant` fails at runtime (model/compatibility), the service falls back to Ollama embeddings automatically.
- For Qdrant Cloud embeddings set `QDRANT_CLOUD_INFERENCE=true`.
