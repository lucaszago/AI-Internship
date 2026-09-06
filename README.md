# Week 2 — RAG Q&A API (Pinecone)

FastAPI service with `POST /ingest`, `GET /debug/retrieve`, and `POST /ask` (citations + refusal), plus a Streamlit UI.

**Vector store:** [Pinecone](https://www.pinecone.io/)  
**Deploy:** [Render](https://render.com) (public HTTPS URL — matches the [Session 1 deploy pattern](https://tailabs.ai/ai-eng-syllabus/week-1/ship-your-first-ai-endpoint-assignment-guide))

**Live URL:** https://week1v2-ask-api-public.onrender.com  

Do **not** post the live URL on LinkedIn or other public posts. Use it only for Maven submission.

---

## Contents

1. [What you get](#what-you-get)
2. [Quick start (local)](#quick-start-local)
3. [One-time Pinecone setup](#one-time-pinecone-setup)
4. [Deploy to Render](#deploy-to-render)
5. [Assignment proof (Maven)](#assignment-proof-maven)

---

## What you get

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Health + RAG config |
| `GET /docs` | Swagger UI |
| `POST /ingest` | Chunk → embed → Pinecone upsert |
| `GET /debug/retrieve?q=...` | Retrieval only (no LLM) |
| `POST /ask` | RAG answer with citations / refusal |
| `POST /ask` + `force_bad: true` | Session 1 guardrail demo |

```text
├── main.py                      # FastAPI app
├── rag/                         # chunk, embed, Pinecone, prompts, routes
├── ui/streamlit_app.py          # Streamlit demo
├── static/index.html            # Same-origin browser UI
├── sample_docs/handbook.txt     # Sample ingest text
├── requirements.txt             # Render / pip install
├── render.yaml                  # Render Blueprint
└── .env.example                 # Copy to .env locally
```

---

## Quick start (local)

```bash
cp .env.example .env
# Edit .env: OPENAI_API_KEY=... and PINECONE_API_KEY=...

uv sync
# or: pip install -r requirements.txt

uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

```bash
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Remote work: up to 3 days per week with manager approval.", "document_id": "handbook"}'

curl -s "http://127.0.0.1:8000/debug/retrieve?q=remote+work+policy" | python3 -m json.tool

curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the remote work policy?"}'

curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the CEO favorite color?"}'
```

Streamlit:

```bash
uv run streamlit run ui/streamlit_app.py
```

Open http://localhost:8501 — sidebar API URL = `http://127.0.0.1:8000`.

---

## One-time Pinecone setup

1. Create a free account at [pinecone.io](https://www.pinecone.io/).
2. Create an API key → put it in `.env` as `PINECONE_API_KEY`.
3. Create a **serverless** index named `document-chunks` (or match `PINECONE_INDEX_NAME`):
   - Dimensions: **1536** (`text-embedding-3-small`)
   - Metric: **cosine**
4. Confirm `/health` shows `"rag_configured": true` and `"pinecone_configured": true`.

---

## Deploy to Render

Follow the same pattern as the [Session 1 assignment guide](https://tailabs.ai/ai-eng-syllabus/week-1/ship-your-first-ai-endpoint-assignment-guide):

1. Push this repo to GitHub (`.env` must stay local — it is gitignored).
2. Go to [render.com](https://render.com) → **New** → **Blueprint** (or **Web Service**).
3. Connect `lucaszago/AI-Internship` and select branch `feature/lzago` (or `main`).
4. Settings (if not using Blueprint):
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Environment variables:
   - `OPENAI_API_KEY`
   - `PINECONE_API_KEY`
   - `PINECONE_INDEX_NAME=document-chunks` (optional if already in `render.yaml`)
6. Wait until **Live**. Live URL:

https://week1v2-ask-api-public.onrender.com

Prove it:

```bash
curl -s https://week1v2-ask-api-public.onrender.com/health

curl -s -X POST https://week1v2-ask-api-public.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAG in one sentence?", "model": "gpt-4o-mini"}'
```

Point Streamlit at that URL for your screenshot.

---

## Assignment proof (Maven)

| # | Proof | How |
| --- | --- | --- |
| 1 | Live URL | Render URL (private to Maven) |
| 2 | Ingest | `POST /ingest` JSON |
| 3 | Retrieval | `GET /debug/retrieve?q=...` JSON |
| 4 | Cited answer | `POST /ask` with a doc question |
| 5 | Refusal | `POST /ask` with an out-of-docs question |
| 6 | Streamlit screenshot | Ingest + Ask tabs (API URL visible) |

```bash
LIVE=https://week1v2-ask-api-public.onrender.com

curl -s -X POST "$LIVE/ingest" -H "Content-Type: application/json" \
  -d '{"text": "Remote work: up to 3 days per week with manager approval.", "document_id": "handbook"}'

curl -s "$LIVE/debug/retrieve?q=remote+work+policy"

curl -s -X POST "$LIVE/ask" -H "Content-Type: application/json" \
  -d '{"question": "What is the remote work policy?"}'

curl -s -X POST "$LIVE/ask" -H "Content-Type: application/json" \
  -d '{"question": "What is the CEO favorite color?"}'
```

---

## Env vars

| Variable | Example | Used by |
| --- | --- | --- |
| `OPENAI_API_KEY` | `sk-...` | Embeddings + LLM |
| `PINECONE_API_KEY` | `pcsk_...` | Vector store |
| `PINECONE_INDEX_NAME` | `document-chunks` | Index name |
| `API_URL` | `https://week1v2-ask-api-public.onrender.com` | Streamlit → API |

Never commit `.env`.
