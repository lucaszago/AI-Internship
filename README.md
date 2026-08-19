# Week 1 v2 — Structured Q&A API

A typed LLM service for the AI Engineering Bootcamp. Callers send a question; the service
returns a validated answer plus tokens, latency, estimated cost, and a retry log.

The same FastAPI process serves both the API and a small web UI. That design is required
for [Databricks Apps](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/):
two separate apps cannot call each other in the browser without an SSO redirect (HTTP 302).

**Live app:** [week1v2-ask-ui](https://week1v2-ask-ui-299177927171866.aws.databricksapps.com)

## Contents

- [What this project is](#what-this-project-is)
- [Architecture](#architecture)
- [API reference](#api-reference)
- [How `/ask` works](#how-ask-works)
- [Local development](#local-development)
- [Databricks Apps](#databricks-apps)
- [Secrets](#secrets)
- [CI and CD](#ci-and-cd)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## What this project is

| Layer | Choice |
| --- | --- |
| Language | Python 3.12+ |
| Package manager | [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`) |
| API | FastAPI in `main.py` |
| UI | Same-origin HTML at `static/index.html` |
| Model provider | OpenAI (`gpt-4o-mini`, `gpt-4o`, `o3-mini`) |
| Host | One Databricks App named `week1v2-ask-ui` |
| Deploy | Databricks Asset Bundle + GitHub Actions |

The HTTP contract matches the bootcamp assignment: top-level `answer`, `tokens_used`,
`cost_usd`, `confidence_score`, `sources_needed`, `model`, `latency_ms`, and `attempts`.
Internally the model still emits a nested Pydantic `Answer` (`answer`, `confidence`,
`sources_needed`). That internal schema is flattened before the HTTP response.

## Architecture

```text
                    ┌──────────────────────────────────────┐
  Browser / curl ─► │ FastAPI  (one process, one origin)   │
                    │                                      │
                    │  GET  /         static/index.html    │
                    │  GET  /health   liveness + key flag  │
                    │  GET  /docs     OpenAPI UI           │
                    │  POST /ask      validate → OpenAI    │
                    └───────────────────┬──────────────────┘
                                        │
                                        ▼
                                 OpenAI Chat Completions
                                 (structured output + retry)
```

**Local:** `uvicorn main:app --host 127.0.0.1 --port 8000`

**Databricks Apps:** `python main.py` binds `0.0.0.0:$DATABRICKS_APP_PORT`. The platform
injects that port. Binding `127.0.0.1` or a hardcoded port causes a 502.

**Why one app, not Streamlit + FastAPI as two apps**

Databricks Apps sit behind SSO. A UI on `week1v2-ask-ui-….databricksapps.com` that
`fetch`es `week1v2-ask-api-….databricksapps.com` does not send the session cookie.
The API returns **302 to login**, not JSON. Serving UI and `/ask` from one origin
avoids that.

## API reference

Base URL locally: `http://127.0.0.1:8000`  
Base URL hosted: `https://week1v2-ask-ui-299177927171866.aws.databricksapps.com`

OpenAPI: `{base}/docs`

### `GET /health`

Does not call OpenAI. Use this to confirm the process is up and whether the key is present.

```json
{
  "status": "ok",
  "openai_key_configured": true
}
```

`openai_key_configured` is `true` when `OPENAI_API_KEY` is set (from `.env` locally, or
from the Databricks secret at runtime). It does not prove the key is valid.

### `POST /ask`

**Request**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `question` | string (min length 1) | yes | — | User question |
| `model` | `"gpt-4o-mini"` \| `"gpt-4o"` \| `"o3-mini"` | no | `gpt-4o-mini` | Chat model |
| `force_bad` | boolean | no | `false` | Force malformed JSON on attempt 1 |

**Response (200)**

| Field | Type | Description |
| --- | --- | --- |
| `answer` | string | Final answer text |
| `tokens_used` | integer | Prompt + completion tokens across attempts |
| `cost_usd` | float | Estimate from hardcoded per-1K prices |
| `confidence_score` | float 0–1 | Model-reported confidence |
| `sources_needed` | boolean | Whether citations would help |
| `model` | string | Model actually used |
| `latency_ms` | integer | Wall time for the whole `/ask` call |
| `attempts` | array | Per-attempt validation log |

Each `attempts[]` item:

| Field | Type | Description |
| --- | --- | --- |
| `attempt` | integer | 1-based |
| `step` | string | `forced_bad_json` or `structured_output` |
| `ok` | boolean | Whether that attempt passed validation |
| `message` | string | Human-readable outcome |
| `raw_output` | string \| null | Model text (forced-bad path) |
| `validation_error` | string \| null | Pydantic error if validation failed |

**Happy-path example**

```bash
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAG in one sentence?", "model": "gpt-4o-mini"}'
```

```json
{
  "answer": "Retrieval-Augmented Generation combines retrieval with generation...",
  "tokens_used": 140,
  "cost_usd": 0.000044,
  "confidence_score": 0.95,
  "sources_needed": false,
  "model": "gpt-4o-mini",
  "latency_ms": 1200,
  "attempts": [
    {
      "attempt": 1,
      "step": "structured_output",
      "ok": true,
      "message": "Structured output matched the Answer schema.",
      "raw_output": null,
      "validation_error": null
    }
  ]
}
```

**Guardrail example**

```bash
curl -s -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is a vector database?", "force_bad": true}'
```

Attempt 1 records a validation failure. Attempt 2 uses structured output and should succeed.

**Errors**

| Status | When | Body |
| --- | --- | --- |
| `422` | Empty `question`, unknown `model`, or other Pydantic request errors | FastAPI `detail` list |
| `502` | Both attempts failed schema validation | `{ "detail": "Model response failed..." }` |
| `503` | `OPENAI_API_KEY` missing | `{ "detail": "OPENAI_API_KEY is not set..." }` |

## How `/ask` works

```text
POST /ask
   │
   ├─ no OPENAI_API_KEY  → 503
   ├─ invalid body       → 422
   │
   └─ loop up to 2 attempts
         │
         ├─ force_bad and attempt 1
         │     call chat.completions.create (plain JSON, bad confidence type)
         │     validate with Answer.model_validate_json
         │     fail → record attempt, continue
         │
         └─ otherwise
               call chat.completions.parse (response_format=Answer)
               flatten to AskResponse
               return 200
```

**Cost estimate** (USD per 1K tokens, hardcoded in `main.py`):

| Model | Input | Output |
| --- | --- | --- |
| `gpt-4o-mini` | 0.00015 | 0.0006 |
| `gpt-4o` | 0.0025 | 0.01 |
| `o3-mini` | 0.0011 | 0.0044 |

These are classroom approximations, not live billing.

## Local development

**Prerequisites**

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An OpenAI API key

**Install and configure**

```bash
uv sync
cp .env.example .env
```

Put the key in `.env`:

```bash
OPENAI_API_KEY=sk-...
```

Never commit `.env`. Git and Databricks both ignore it.

**Run**

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

| URL | What |
| --- | --- |
| http://127.0.0.1:8000 | Web UI |
| http://127.0.0.1:8000/docs | Swagger |
| http://127.0.0.1:8000/health | Liveness |

Production-style start (same as Databricks):

```bash
DATABRICKS_APP_PORT=8000 uv run python main.py
```

**Smoke test** (no OpenAI call; checks `/`, `/health`, `/docs`)

```bash
uv run python smoke_test.py
```

## Databricks Apps

App name: `week1v2-ask-ui`  
Bundle name: `question-answer-demo-app`  
Bundle resource key: `ask_ui`  
Target: `prod`

### Prerequisites

- Databricks CLI 1.12+ (`databricks -v`)
- A CLI profile (`databricks auth login --profile YOUR_PROFILE`)
- Apps enabled on the workspace
- Permission to create/manage apps

### Secret (one-time)

```bash
databricks secrets create-scope week1v2 --profile YOUR_PROFILE

databricks secrets put-secret week1v2 openai_api_key \
  --string-value "$OPENAI_API_KEY" \
  --profile YOUR_PROFILE
```

The Environment tab in the Apps UI does **not** have an Add button. Keys are injected
from a **secret resource** declared in `databricks.yml` and referenced in `app.yaml`.

### Deploy from your laptop

```bash
cd ai-engineering-bootcamp-v2/week-1v2

databricks bundle validate --target prod --profile YOUR_PROFILE
databricks bundle deploy --target prod --profile YOUR_PROFILE
databricks bundle run ask_ui --target prod --profile YOUR_PROFILE
```

`bundle deploy` uploads code and config. It does **not** restart the process.
`bundle run ask_ui` starts or restarts the app. Always run both after a code change.

Useful follow-ups:

```bash
databricks apps get week1v2-ask-ui --profile YOUR_PROFILE
databricks apps logs week1v2-ask-ui --profile YOUR_PROFILE
```

### Config files

| File | Role |
| --- | --- |
| `databricks.yml` | Bundle: app name, workspace host, secret resource, env binding, `bundle_owner` |
| `app.yaml` | Runtime: `python main.py` and `OPENAI_API_KEY` from `value_from: openai_api_key` |
| `.databricksignore` | Exclude `.env`, `.venv`, `.databricks/` from upload |

`bundle_owner` defaults to `lukaszago@hotmail.com` so CI deploys to the same Workspace
path as the original app owner. Override with:

```bash
databricks bundle deploy --target prod --var="bundle_owner=you@example.com"
```

### What is not uploaded

Local `.env` never goes to Databricks. If Ask returns 503 on the hosted URL, the secret
scope is missing or the app cannot read it.

## Secrets

There are two secret stores. Mixing them up is the usual failure mode.

| Store | Names | Used by |
| --- | --- | --- |
| Laptop `.env` | `OPENAI_API_KEY` | Local uvicorn |
| Databricks secret scope `week1v2` | key `openai_api_key` | Running app |
| GitHub environment `prod` | `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET` | GitHub Actions deploy only |

GitHub does **not** need the OpenAI key. The app reads OpenAI from Databricks at runtime.

## CI and CD

Workflows live in `.github/workflows/` at the repository root (same folder as `main.py`).

| Workflow | File | When | What |
| --- | --- | --- | --- |
| CI | `.github/workflows/ci.yml` | Every PR and every push to `main` | `uv sync --frozen` + `smoke_test.py` |
| Deploy | `.github/workflows/deploy.yml` | Push to `main`, or **Run workflow** | Validate, deploy, restart app, wait until `RUNNING` |

CI never deploys. Deploy never calls OpenAI during the job; it only ships code.

### Will the app update automatically?

Yes, after Deploy succeeds on `main`:

```text
merge / push to main
        │
        ▼
  GitHub Actions “Deploy”
        │
        ├─ databricks bundle validate
        ├─ databricks bundle deploy --auto-approve
        ├─ databricks bundle run ask_ui     ← this restarts the app
        └─ poll databricks apps get until state == RUNNING
```

Pushes to feature branches do **not** deploy. Manual runs: **Actions → Deploy → Run workflow**
on branch `main`.

### One-time GitHub setup

1. Databricks: create a **service principal**. Grant **CAN MANAGE** on `week1v2-ask-ui`
   and **CAN READ** on secret scope `week1v2`.
2. GitHub: **Settings → Environments → `prod`**. Add secrets (not variables):

   | Secret | Example |
   | --- | --- |
   | `DATABRICKS_HOST` | `https://dbc-d3858b75-976f.cloud.databricks.com` |
   | `DATABRICKS_CLIENT_ID` | Service principal application ID |
   | `DATABRICKS_CLIENT_SECRET` | Service principal OAuth secret |

3. Auth type in the workflow is `oauth-m2m` (client ID + secret). Databricks also supports
   [GitHub OIDC](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/cicd-github-actions)
   if you want to drop the client secret later.

4. If `bundle deploy` returns **409 ALREADY_EXISTS**, bind once from a laptop:

   ```bash
   databricks bundle deployment bind ask_ui week1v2-ask-ui --target prod --auto-approve
   ```

### GitHub Action CLI install

The workflow uses:

```yaml
- uses: databricks/setup-cli@main
  with:
    version: 1.12.1
```

There is **no** `databricks/setup-cli@v1` tag. Using `@v1` fails in **Set up job** before
any Databricks command runs.

## Project structure

```text
.
├── .github/workflows/
│   ├── ci.yml              # Smoke test
│   └── deploy.yml          # Bundle deploy + app restart
├── main.py                 # FastAPI: /, /health, /ask
├── static/index.html       # Hosted UI (fetch /ask on same origin)
├── smoke_test.py           # CI: start API, hit /, /health, /docs
├── app.yaml                # Databricks Apps start command + env
├── databricks.yml          # Bundle resource + secret
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── .databricksignore
└── README.md
```

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Hosted Ask: `OPENAI_API_KEY is not set` | `.env` is local-only | Put key in scope `week1v2` / `openai_api_key`, then `bundle deploy` + `bundle run` |
| Hosted Ask: 302 HTML login page | UI called a **second** app URL | Use this single-app design; `fetch("/ask")` |
| Databricks 502 | Wrong host/port | `python main.py` must listen on `0.0.0.0` and `DATABRICKS_APP_PORT` |
| Local 503 | Missing `.env` | `cp .env.example .env` and set the key |
| Local 422 | Empty question or bad model name | Use `gpt-4o-mini`, `gpt-4o`, or `o3-mini` |
| `409 ALREADY_EXISTS` | Bundle tried to create an app that already exists | Bind `ask_ui` to `week1v2-ask-ui`; do not rename the resource key |
| GitHub Deploy fails in **Set up job** on `@v1` | Invalid action tag | Use `databricks/setup-cli@main` (already in `deploy.yml` on `feature/lzago`) |
| GitHub Deploy still uses `@v1` | Fix not merged to `main` | Merge the pin PR, then re-run Deploy on `main` |
| Deploy job 403 | SP cannot manage the app | Grant the GitHub SP **CAN MANAGE** on `week1v2-ask-ui` |
| App deploys but still serves old UI | Skipped `bundle run` | Restart with `databricks bundle run ask_ui --target prod` |
| Port 8000 in use locally | Another process | Stop it or pass `--port 8001` |

## License

Part of the AI Engineering Bootcamp internship repository.
