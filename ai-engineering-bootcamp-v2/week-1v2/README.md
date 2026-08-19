# Week 1 v2 — Structured Q&A API

A production-style LLM service built for the AI Engineering Bootcamp. The app exposes a typed
`/ask` endpoint with structured output validation, guardrail retries, and observability
(tokens, latency, cost). It runs locally with FastAPI and deploys as a single
[Databricks App](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/).

## Features

- **Structured responses** — OpenAI structured output validated with Pydantic
- **Guardrail demo** — optional `force_bad` flag triggers validation failure and retry
- **Observability** — per-request tokens, latency, estimated cost, and attempt log
- **Same-origin UI** — web UI and API share one process (required for Databricks Apps SSO)
- **CI** — GitHub Actions smoke test (no OpenAI calls)
- **Databricks deployment** — bundle + secret scope, no keys in git

## Architecture

```text
Browser / curl
     │
     ▼
┌─────────────────────────────────────┐
│  FastAPI (main.py)                  │
│  GET  /         → static/index.html │
│  GET  /health   → status            │
│  POST /ask      → OpenAI + validate │
└─────────────────────────────────────┘
     │
     ▼
 OpenAI API (gpt-4o-mini | gpt-4o | o3-mini)
```

Locally you run uvicorn. On Databricks Apps the runtime executes `python main.py`, which
binds to `0.0.0.0:$DATABRICKS_APP_PORT`.

## API reference

### `GET /health`

Returns service status. Does not call OpenAI.

```json
{
  "status": "ok",
  "openai_key_configured": true
}
```

### `POST /ask`

**Request body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `question` | string | yes | Non-empty question |
| `model` | string | no | `gpt-4o-mini` (default), `gpt-4o`, or `o3-mini` |
| `force_bad` | boolean | no | Demo flag: force malformed JSON on first attempt |

**Response body (200)**

| Field | Type | Description |
| --- | --- | --- |
| `answer` | string | Model answer text |
| `tokens_used` | integer | Total tokens for the request |
| `cost_usd` | float | Estimated cost (USD) |
| `confidence_score` | float | Model confidence (0–1) |
| `sources_needed` | boolean | Whether citations would help |
| `model` | string | Model used |
| `latency_ms` | integer | End-to-end latency |
| `attempts` | array | Validation/retry log |

**Example**

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
      "message": "Structured output matched the Answer schema."
    }
  ]
}
```

**Error responses**

| Status | When |
| --- | --- |
| `422` | Invalid input (empty question, unknown model) |
| `502` | Model output failed validation after retry |
| `503` | `OPENAI_API_KEY` not configured |

Interactive docs: `http://127.0.0.1:8000/docs`

## Local development

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
cd ai-engineering-bootcamp-v2/week-1v2
uv sync
cp .env.example .env   # add OPENAI_API_KEY
```

**Run the app**

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

- UI: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

**Smoke test (no OpenAI calls)**

```bash
uv run python smoke_test.py
```

**Optional Streamlit client** (separate process, for classroom demos)

```bash
uv sync --extra ui
uv run streamlit run demo_page.py
```

## Databricks Apps deployment

This project deploys as **one app** (`week1v2-ask-ui`). UI and API share the same origin so
browser requests do not hit SSO redirects between two app URLs.

**Prerequisites**

- Databricks CLI v1.0+ with an authenticated profile
- Apps enabled in your workspace
- A secret scope with your OpenAI key

**1. Store the API key in a secret scope**

```bash
databricks secrets create-scope week1v2 --profile YOUR_PROFILE

databricks secrets put-secret week1v2 openai_api_key \
  --string-value "$OPENAI_API_KEY" \
  --profile YOUR_PROFILE
```

**2. Configure the bundle**

Edit `databricks.yml` — set your workspace host under `targets.prod.workspace.host` if
needed. The default uses `${workspace.current_user.userName}` for the bundle path.

**3. Deploy and start**

```bash
databricks bundle validate --target prod --profile YOUR_PROFILE
databricks bundle deploy --target prod --profile YOUR_PROFILE
databricks bundle run ask_ui --target prod --profile YOUR_PROFILE
```

The CLI prints the app URL when the deployment succeeds.

**Secrets wiring**

| File | Purpose |
| --- | --- |
| `databricks.yml` | Declares secret resource + env binding for bundle deploy |
| `app.yaml` | Runtime command and env for the Databricks Apps platform |

Local `.env` is **not** uploaded (see `.databricksignore`). Use the secret scope for hosted runs.

## CI

GitHub Actions runs on push/PR to `main`:

```yaml
uv sync --frozen
uv run python smoke_test.py
```

Workflow: `.github/workflows/ci.yml`

## CD (GitHub Actions → Databricks)

Automated deploys use `.github/workflows/deploy.yml`. On push to `main` (when `week-1v2/`
changes) or manual trigger, the workflow:

1. Validates the bundle
2. Deploys with `databricks bundle deploy`
3. Restarts the app with `databricks bundle run ask_ui`
4. Polls until the app is `RUNNING`

### One-time setup

**1. Create a service principal (if you do not have one)**

In Databricks: **User management → Service principals → Add service principal**.

Grant it:

- **CAN MANAGE** on app `week1v2-ask-ui`
- **CAN READ** on secret scope `week1v2` (Apps inject secrets at runtime)

**2. Create a GitHub environment**

Repo → **Settings → Environments → New environment** → name it `prod`.

Add these **secrets** (not variables):

| Secret | Value |
| --- | --- |
| `DATABRICKS_HOST` | `https://dbc-d3858b75-976f.cloud.databricks.com` |
| `DATABRICKS_CLIENT_ID` | Service principal application (client) ID |
| `DATABRICKS_CLIENT_SECRET` | Service principal OAuth secret |

**3. Match bundle owner**

`databricks.yml` uses `bundle_owner` (default: `lukaszago@hotmail.com`) for the workspace
path. That must match whoever originally created the app. Override if needed:

```bash
databricks bundle deploy --target prod --var="bundle_owner=you@example.com"
```

**4. Bind existing app (only if deploy fails with 409)**

Run once locally:

```bash
databricks bundle deployment bind ask_ui week1v2-ask-ui --target prod --auto-approve
```

### Run a deploy

**Manual (recommended first time)**

GitHub → **Actions → Deploy → Run workflow**.

**Automatic**

Merge to `main` with changes under `ai-engineering-bootcamp-v2/week-1v2/`.

### Optional: require approval before prod

In **Settings → Environments → prod → Deployment protection rules**, enable **Required
reviewers**. Each deploy waits for approval before running.

### Optional: upgrade to OIDC (no client secret)

Databricks recommends [GitHub OIDC federation](https://docs.databricks.com/aws/en/dev-tools/auth/provider-github)
instead of a long-lived secret. That swaps `oauth-m2m` for `github-oidc` and drops
`DATABRICKS_CLIENT_SECRET`. See the [official Apps CI/CD guide](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/cicd-github-actions).

## Project structure

```text
week-1v2/
├── main.py              # FastAPI app: /ask, /health, /
├── static/index.html    # Hosted web UI
├── demo_page.py         # Optional local Streamlit client
├── smoke_test.py        # CI smoke test
├── app.yaml             # Databricks Apps runtime config
├── databricks.yml       # Bundle: app resource + secret binding
├── pyproject.toml       # Dependencies (uv)
├── uv.lock              # Locked deps for reproducible builds
├── .env.example         # Local env template
├── stages/              # Incremental teaching versions (not deployed)
│   ├── stage_1_bare_ask.py
│   ├── stage_2_structured_output.py
│   └── stage_3_guardrails_and_observability.py
└── README.md
```

The `stages/` folder shows how the endpoint evolved step by step during the bootcamp. Only
`main.py` is deployed.

## Guardrail demo

Enable **Force a bad first response** in the UI, or send `"force_bad": true` in the request
body. The API:

1. Asks the model for intentionally malformed JSON
2. Validates with Pydantic and records the failure in `attempts`
3. Retries with OpenAI structured output

This demonstrates a production pattern: never trust raw LLM output at your API boundary.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `OPENAI_API_KEY is not set` (hosted) | Add secret to scope `week1v2` / key `openai_api_key`, redeploy |
| `OPENAI_API_KEY` error (local) | Create `.env` from `.env.example` |
| 502 on Databricks | App must bind `0.0.0.0`; use `python main.py` (already in `app.yaml`) |
| 302 between two app URLs | Use one app for UI + API (this repo's design) |
| `409 ALREADY_EXISTS` on deploy | Keep bundle resource key `ask_ui`; do not rename without rebinding |
| Port 8000 in use locally | Stop other servers or pick another port |

## License

Part of the AI Engineering Bootcamp internship repository.
