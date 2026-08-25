# Week 2 — RAG Q&A API (Databricks AI Search)

Session 2 RAG assignment for the [AI Engineering Bootcamp](https://tailabs.ai/ai-eng-syllabus/week-2/week-2-rag-assignment-guide). Extends Session 1 `POST /ask` with document ingest, retrieval debug, citations, and refusal.

**Vector store:** Databricks AI Search (Delta Sync) + Unity Catalog — not Pinecone.

**Live app:** [week1v2-ask-ui](https://week1v2-ask-ui-299177927171866.aws.databricksapps.com)

Do **not** post the live URL publicly (LinkedIn, etc.). Use it only for Maven submission.

---

## Contents

1. [Folder layout](#folder-layout)
2. [Quick start (local)](#quick-start-local)
3. [One-time Databricks setup](#one-time-databricks-setup)
4. [API reference](#api-reference)
5. [Streamlit UI](#streamlit-ui)
6. [Deploy to Databricks](#deploy-to-databricks)
7. [Assignment proof (Maven)](#assignment-proof-maven)
8. [Environment variables](#environment-variables)
9. [Troubleshooting](#troubleshooting)

---

## Folder layout

```text
AI-Internship/
├── main.py                      # FastAPI app (/, /health, /ingest, /debug/retrieve, /ask)
├── rag/                         # RAG library
│   ├── config.py                # Env vars → table/index names
│   ├── chunking.py              # Text splitter
│   ├── embeddings.py            # OpenAI embeddings
│   ├── store.py                 # Write chunks to Delta
│   ├── search.py                # sync_index + query_index
│   ├── prompts.py               # Grounding prompt + refusal
│   ├── ingest.py                # End-to-end ingest
│   └── routes.py                # Request/response models + handlers
├── ui/
│   └── streamlit_app.py         # Demo UI (calls the API only)
├── scripts/
│   ├── setup_delta_table.py     # Create Unity Catalog Delta table
│   └── batch_ingest.py          # Ingest a folder of .txt/.md files
├── notebooks/
│   └── setup_ai_search.ipynb    # Create endpoint + index; verify sync/query
├── sample_docs/
│   └── handbook.txt             # Small test document
├── static/
│   └── index.html               # Same-origin browser UI on Databricks Apps
├── smoke_test.py                # CI health check (no OpenAI/Databricks)
├── app.yaml                     # Databricks Apps runtime env
├── databricks.yml               # Bundle: app + resources + secrets
├── .env.example                 # Copy to .env locally
└── README.md
```

| Path | Purpose |
| --- | --- |
| `main.py` | HTTP routes — keep thin |
| `rag/` | All RAG logic |
| `ui/` | Streamlit demo (local / screenshot) |
| `scripts/` | One-off setup + batch tools |
| `notebooks/` | Databricks AI Search setup |
| `sample_docs/` | Test corpus |

---

## Quick start (local)

Always run commands from the **repo root** (the folder that contains `main.py`).

```bash
cd /Users/lucaszago/Downloads/ai_learning/AI-Internship
```

### 1. Install

```bash
uv sync
cp .env.example .env
```

Edit `.env`:

```bash
OPENAI_API_KEY=sk-...
DATABRICKS_CONFIG_PROFILE=dbx-lzago-ai
```

```bash
databricks auth login --profile dbx-lzago-ai
```

### 2. Infra (skip if already done)

```bash
uv run python scripts/setup_delta_table.py
# Then create endpoint + index via notebooks/setup_ai_search.ipynb
```

### 3. Start API

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

- Swagger: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  

### 4. Smoke the RAG loop

```bash
# Ingest
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Remote work: up to 3 days per week with manager approval.", "document_id": "handbook"}'

# Wait 1–2 minutes for index sync, then retrieve (no LLM)
curl -s "http://127.0.0.1:8000/debug/retrieve?q=remote+work+policy" | python3 -m json.tool

# Cited answer
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the remote work policy?"}' | python3 -m json.tool

# Refusal
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the CEO salary?"}' | python3 -m json.tool
```

### 5. Streamlit

Keep the API running, then in a **second terminal**:

```bash
cd /Users/lucaszago/Downloads/ai_learning/AI-Internship
uv run streamlit run ui/streamlit_app.py
```

Open http://localhost:8501 — sidebar API URL = `http://127.0.0.1:8000`.

---

## One-time Databricks setup

| Object | Name |
| --- | --- |
| Catalog | `workspace` |
| Schema | `document_retrieval` |
| Delta table | `workspace.document_retrieval.document_chunks` |
| AI Search endpoint | `document-chunks-search-endpoint` |
| AI Search index | `workspace.document_retrieval.document_chunks_index` |
| Embeddings | `text-embedding-3-small` (1536 dims) |

**Free Edition:** use **Delta Sync** (TRIGGERED). Direct Access / `upsert` is not available.

1. `uv run python scripts/setup_delta_table.py`
2. Run `notebooks/setup_ai_search.ipynb` (endpoint → index → sync → query)

---

## Architecture

```text
POST /ingest
  → chunk → embed → append Delta → sync_index()

GET /debug/retrieve?q=...
  → embed question → query_index → return chunks (no LLM)

POST /ask
  → retrieve → grounding prompt → structured LLM
  → answer + citations + retrieved_chunk_ids + refused
```

---

## API reference

Local base: `http://127.0.0.1:8000` · OpenAPI: `/docs`

### `GET /health`

Returns `openai_key_configured`, `rag_configured`, and resolved RAG names. No external calls.

### `POST /ingest`

| Field | Required | Description |
| --- | --- | --- |
| `text` | yes | Document body |
| `document_id` | yes | Stable ID (re-ingest replaces old chunks) |
| `source` | no | Optional label / filename |

```json
{"document_id": "handbook", "chunks_indexed": 1, "status": "indexed"}
```

### `GET /debug/retrieve?q=...`

Top-k chunks + scores. Use this **before** debugging `/ask`.

### `POST /ask`

RAG by default. Response includes Session 1 fields plus:

| Field | Description |
| --- | --- |
| `citations` | `document_id` values the model cited |
| `retrieved_chunk_ids` | Chunk IDs from search |
| `refused` | `true` when answer is the refusal phrase |

Refusal phrase: `I don't have enough information to answer that.`

`force_bad: true` still runs the Session 1 guardrail demo (skips RAG).

---

## Streamlit UI

```bash
uv run streamlit run ui/streamlit_app.py
```

| Tab | What it does |
| --- | --- |
| Ingest | Calls `POST /ingest` |
| Ask | Calls `POST /ask` — shows citations / refusal |
| Debug retrieve | Calls `GET /debug/retrieve` |

Optional `.env`:

```bash
API_URL=http://127.0.0.1:8000
# After deploy, you can set the Databricks App URL (SSO may apply)
```

Streamlit is a **thin client**. All RAG logic stays in FastAPI.

---

## Deploy to Databricks

Deploys **FastAPI only** (`main.py` + `rag/` + `static/`). Streamlit stays on your laptop for demos/screenshots.

### Prerequisites

- [ ] CLI: `databricks -v` (1.12+)
- [ ] Auth: `databricks auth login --profile dbx-lzago-ai`
- [ ] Secret scope `week1v2` / key `openai_api_key`
- [ ] Phase 0 table + AI Search index exist

### One-time secret

```bash
databricks secrets create-scope week1v2 --profile dbx-lzago-ai

databricks secrets put-secret week1v2 openai_api_key \
  --string-value "$OPENAI_API_KEY" \
  --profile dbx-lzago-ai
```

### Deploy (laptop)

```bash
cd /Users/lucaszago/Downloads/ai_learning/AI-Internship

databricks bundle validate --target prod --profile dbx-lzago-ai
databricks bundle deploy --target prod --profile dbx-lzago-ai
databricks bundle run ask_ui --target prod --profile dbx-lzago-ai
```

| Command | What it does |
| --- | --- |
| `bundle validate` | Check YAML |
| `bundle deploy` | Upload code + config |
| `bundle run ask_ui` | **Restart** the app (required after code changes) |

### Check status

```bash
databricks apps get week1v2-ask-ui --profile dbx-lzago-ai
databricks apps logs week1v2-ask-ui --profile dbx-lzago-ai
```

Wait until state = `RUNNING`, then open:

https://week1v2-ask-ui-299177927171866.aws.databricksapps.com

### App resources (auto permissions)

| Resource | Grants |
| --- | --- |
| `openai_api_key` | READ secret |
| `document_chunks_index` | SELECT on AI Search index |
| `document_chunks_table` | MODIFY on Delta table |

### After deploy — prove live API

Open the app in a browser while logged into Databricks, or use the hosted UI at `/`.

```bash
# Health
curl -s https://week1v2-ask-ui-299177927171866.aws.databricksapps.com/health

# Ingest on LIVE URL (not localhost)
curl -s -X POST https://week1v2-ask-ui-299177927171866.aws.databricksapps.com/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Remote work: up to 3 days per week with manager approval.", "document_id": "handbook"}'
```

Wait 1–2 minutes, then hit `/debug/retrieve` and `/ask` on the **same live host**.

### GitHub deploy (optional)

Push to `main` runs `.github/workflows/deploy.yml` if GitHub environment `prod` has:

- `DATABRICKS_HOST`
- `DATABRICKS_CLIENT_ID`
- `DATABRICKS_CLIENT_SECRET`

---

## Assignment proof (Maven)

Per the [Session 2 guide](https://tailabs.ai/ai-eng-syllabus/week-2/week-2-rag-assignment-guide), submit to **Maven only** (not LinkedIn):

### What to collect

| # | Proof | How |
| --- | --- | --- |
| 1 | Live URL | Databricks App URL (private to Maven) |
| 2 | Ingest works | curl JSON from **live** `POST /ingest` |
| 3 | Retrieval works alone | curl JSON from **live** `GET /debug/retrieve?q=...` |
| 4 | Cited answer | curl JSON from **live** `POST /ask` with a doc question |
| 5 | Refusal | curl JSON from **live** `POST /ask` with an out-of-docs question |
| 6 | Streamlit screenshot | Ingest + Ask tabs (API URL in sidebar visible) |

### Exact commands (save the JSON)

Replace `LIVE` with your Databricks App URL.

```bash
LIVE=https://week1v2-ask-ui-299177927171866.aws.databricksapps.com

# 1) Ingest
curl -s -X POST "$LIVE/ingest" \
  -H "Content-Type: application/json" \
  -d '{"text": "Remote work: up to 3 days per week with manager approval.", "document_id": "handbook"}' \
  | tee proof_ingest.json

# Wait 1–2 minutes

# 2) Retrieval only
curl -s "$LIVE/debug/retrieve?q=remote+work+policy" | tee proof_retrieve.json

# 3) Cited answer
curl -s -X POST "$LIVE/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the remote work policy?"}' \
  | tee proof_ask_cited.json

# 4) Refusal
curl -s -X POST "$LIVE/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the CEO salary?"}' \
  | tee proof_ask_refusal.json
```

### What “good” looks like

**Cited ask** — expect something like:

- `"answer"` mentions 3 days / manager approval
- `"citations": ["handbook"]`
- `"retrieved_chunk_ids": ["handbook::0"]`
- `"refused": false`

**Refusal** — expect:

- `"answer": "I don't have enough information to answer that."`
- `"refused": true`

### Streamlit screenshot

1. API running (local or live URL in sidebar)
2. **Ingest** tab — success message after ingest
3. **Ask** tab — cited answer visible
4. Crop so the URL / result is readable

### Maven paste template

```text
Session 2 RAG (Databricks AI Search)

Live URL: https://week1v2-ask-ui-….databricksapps.com

1) Ingest:   [paste proof_ingest.json]
2) Retrieve: [paste proof_retrieve.json]
3) Cited ask: [paste proof_ask_cited.json]
4) Refusal:  [paste proof_ask_refusal.json]
5) Streamlit: [attach screenshot]
```

### Checklist

- [ ] Session 1 `/ask` still works (extended, not replaced blindly)
- [ ] `POST /ingest` with `text` + `document_id`
- [ ] Retrieval tested alone (`/debug/retrieve`)
- [ ] `/ask` cites sources and refuses when context is missing
- [ ] Proofs run against **live** Databricks URL (not only localhost)
- [ ] Streamlit screenshot ready
- [ ] Submitted to Maven only — no public live URL

---

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | Embeddings + chat |
| `RAG_CATALOG` | `workspace` | Catalog |
| `RAG_SCHEMA` | `document_retrieval` | Schema |
| `RAG_TABLE` | `document_chunks` | Delta table |
| `VECTOR_SEARCH_ENDPOINT` | `document-chunks-search-endpoint` | Endpoint |
| `VECTOR_SEARCH_INDEX` | `…document_chunks_index` | Index (injected on Apps) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Must match index (1536) |
| `RAG_CHUNK_SIZE` | `800` | Chunk size |
| `RAG_CHUNK_OVERLAP` | `100` | Overlap |
| `RAG_TOP_K` | `5` | Retrieve count |
| `DATABRICKS_CONFIG_PROFILE` | — | Local CLI profile |
| `API_URL` | `http://127.0.0.1:8000` | Streamlit → API |

Never commit `.env`.

---

## Secrets

| Store | Used by |
| --- | --- |
| Laptop `.env` | Local uvicorn / Streamlit |
| Databricks scope `week1v2` / `openai_api_key` | Hosted app |
| GitHub `prod` (`DATABRICKS_*`) | CI deploy only |

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Could not import module "main"` | `cd` to repo root (folder with `main.py`) |
| Empty retrieve after ingest | Wait 1–2 min for sync |
| Local ingest 502 / auth errors | `databricks auth login --profile dbx-lzago-ai` |
| Hosted 503 OpenAI key | Put secret in `week1v2` / `openai_api_key`, redeploy + `bundle run` |
| Hosted ingest/ask 502 | Redeploy so app SP gets table MODIFY + index SELECT |
| App serves old code | You forgot `databricks bundle run ask_ui` |
| Wrong chunks | Fix with `/debug/retrieve` before changing prompts |

---

## License

Part of the AI Engineering Bootcamp internship repository.
