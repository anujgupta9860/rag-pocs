# POC 1 — OpenRAG on your local Mac

**What:** [OpenRAG](https://github.com/langflow-ai/openrag) (openr.ag) —
Docling parses, OpenSearch indexes (hybrid vector + BM25), Langflow orchestrates.
**Where:** directly on macOS (Apple Silicon). No VM, no cloud account needed.
**Time:** ~30–60 min first run (image pulls dominate), ~5 min after that.

Upstream is **not vendored** in this repo. `start.sh` clones it at a pinned tag
into `./upstream/` and runs its own compose file, so you test the real project.

---

## 1. Prerequisites

- macOS on Apple Silicon, **≥ 50 GB free disk**, Docker Desktop running
  (or Podman — upstream supports both; commands below use Docker).
- Docker Desktop → Settings → Resources: **4 CPU, 10–12 GB RAM**.
- One LLM + embedding provider key (OpenAI, Anthropic, Gemini, Azure,
  watsonx… any Langflow-supported provider), or a local Ollama.
  **Use the same providers/models you use for the RAGFlow POC.**
- Ports free: **3000** (UI), **8000** (backend API), **7860** (Langflow),
  **9200** (OpenSearch), **5601** (OpenSearch Dashboards), **5001** (Docling).
  Check: `bash ../common/scripts/check-local.sh`

## 2. Configure

```bash
cd openrag-poc
cp .env.example .env
# Edit .env: set OPENRAG_TAG if you want a different release,
# and the provider key(s) for your chat + embedding models.
```

Decide **now**: Basic setup (no auth, everyone sees all docs — fine for a
laptop POC) vs Advanced/OAuth setup (per-user document access — needed if you
want to evaluate access control). Switching later means re-setup.

## 3. Run it

```bash
./start.sh
```

What `start.sh` does, in order:

1. Clones `langflow-ai/openrag` into `./upstream/` (or `git pull`s it) and
   checks out `$OPENRAG_TAG`.
2. Copies your `.env` into the upstream checkout if upstream has none.
3. Ensures the Langflow superuser is set in the upstream `.env`. Langflow
   exits if `LANGFLOW_SUPERUSER_PASSWORD` is empty (and the UI then hangs
   on "Starting OpenRAG…" — see Troubleshooting), so if it's unset,
   `start.sh` generates a random password and saves it to
   `langflow-credentials.txt` (git-ignored).
4. `docker compose up -d` (CPU compose file; there is a GPU override upstream
   which does not apply to Macs).
5. Waits until `http://localhost:3000` responds, then prints all URLs.

Then open **http://localhost:3000** and finish onboarding in the UI:
choose the chat model and embedding model (the ones in your `.env`), create
your account/API key if prompted (**Settings → API keys** — you need the key
for bench.py and MCP; it looks like `orag_...`).

Manual equivalent, if you prefer to see every step:

```bash
git clone https://github.com/langflow-ai/openrag.git upstream
cd upstream && git checkout v0.3.0        # = OPENRAG_TAG default
cp ../.env .env                            # if upstream .env does not exist
docker compose up -d
docker compose ps                          # all services up/healthy?
```

Alternative upstream-native install (Python package + TUI), also supported:

```bash
pip install uv && uv run openrag --tui     # interactive installer/status TUI
# In the TUI you can switch GPU<->CPU mode; on a Mac you want CPU mode.
```

Stop it:

```bash
./stop.sh            # docker compose down (keeps indexed data in volumes)
./stop.sh --wipe     # docker compose down -v (deletes the OpenSearch index too)
```

## 4. Ingest files

### 4a. In the UI (do this first, once, by hand)

1. http://localhost:3000 → **Knowledge** → **Upload** (drag & drop).
2. Select **all files in `../common/sample-data/`**.
3. Watch processing: each file goes *parsing (Docling) → chunking →
   embedding → indexed*. A file is ingested when its status shows complete.
   **Start your stopwatch at drop, stop it when status flips** — that is your
   manual “time to searchable” cross-check for §6.

### 4b. Via API (what bench.py automates)

Backend REST (proxied by the frontend on :3000; direct backend on :8000
depending on version — check `http://localhost:8000/docs` on your tag):

```bash
# Upload one file (multipart). Field name used by upstream: "files".
curl -X POST http://localhost:3000/upload \
  -H "X-API-Key: $OPENRAG_API_KEY" \
  -F "files=@../common/sample-data/permit-guide.md"

# Search only (no generation) — useful to confirm a doc is searchable:
curl -X POST http://localhost:3000/search \
  -H "X-API-Key: $OPENRAG_API_KEY" -H "Content-Type: application/json" \
  -d '{"query": "solar pump permit setback distance"}'
```

> API note: endpoint paths/payload fields are versioned upstream. If a call
> 404s on your tag, open the FastAPI docs at `:8000/docs`, find the current
> upload/search/chat paths, and update `../common/bench/bench_config.openrag.json`
> (paths live in config, not in bench.py code). Record any change in RESULTS.md.

### 4c. Via Python SDK

```bash
pip install openrag-sdk
```

```python
import asyncio
from openrag_sdk import OpenRAGClient

async def main():
    async with OpenRAGClient() as client:
        r = await client.chat.create(message="What is RAG?")
        print(r.response)

asyncio.run(main())
```

## 5. Test a query

### 5a. UI

**Chat** → ask the 3 smoke queries (`../common/queries/smoke-queries.txt`),
then the 12 gold queries. Click citations — do they open the right document?

### 5b. API

```bash
curl -X POST http://localhost:3000/chat \
  -H "X-API-Key: $OPENRAG_API_KEY" -H "Content-Type: application/json" \
  -d '{"message": "How close to a property line can an Aurora pump be installed?"}'
```

### 5c. MCP (the agent-integration test)

OpenRAG mounts an MCP server at **`/mcp`** on the same instance. Point any
MCP client (Cursor, Claude Desktop, an ADK agent) at it:

```json
{ "mcpServers": { "openrag": {
    "url": "http://localhost:3000/mcp",
    "headers": { "X-API-Key": "orag_your_api_key_here" } } } }
```

It exposes tools for RAG chat, semantic search, ingestion and settings.
Time-box this: note how long from “client configured” to “first tool answer”.

### 5d. Inside the pipeline (Langflow)

http://localhost:7860 — open the *Ingestion* and *Chat/Agent* flows. This is
how you tune OpenRAG: chunk size/overlap, retriever top-K, rerank step and
prompts are nodes in these flows, not config files.

## 6. Measure ingestion time and query time

Definitions are in [`../docs/evaluation-guide.md`](../docs/evaluation-guide.md).
The short version: **upload time** (API accepts the file) is not ingestion;
**time to searchable** (probe search returns the file's unique term) is.

Automated, same harness as RAGFlow:

```bash
pip install -r ../common/bench/requirements.txt
export OPENRAG_API_KEY=orag_...        # from Settings in the UI
python ../common/bench/bench.py --system openrag \
  --base-url http://localhost:3000 \
  --ingest-dir ../common/sample-data \
  --queries ../common/queries/gold-queries.json \
  --repeats 3 --out ../results/openrag
# -> ../results/openrag-ingestion.csv, -queries.csv, -report.md
```

For a clean ingestion number: `./stop.sh --wipe && ./start.sh` first, so the
index is empty, then run bench.py (it uploads everything itself).

Manual stopwatch method (any shell, no Python):

```bash
# Query latency, 3 runs of the same question:
for i in 1 2 3; do
  /usr/bin/time -p curl -s -X POST http://localhost:3000/chat \
    -H "X-API-Key: $OPENRAG_API_KEY" -H "Content-Type: application/json" \
    -d '{"message": "What does the Pro 3000 cost per year on the annual plan?"}' \
    -o /dev/null
done
```

## 7. What to record for the comparison

- Setup time, ingestion per file (report.md), query p50/p95 (report.md)
- Citation quality on the table + permit questions
- One tuning attempt: change chunking in the Langflow ingestion flow,
  re-ingest one file, re-run its gold queries — how long did the loop take?
- MCP integration time (§5c)

## 8. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Container OOM / services restart | Docker Desktop memory too low — raise to 10–12 GB (upstream minimum for its VM is 8 GB; Podman: `podman machine init --memory 8192`+). Or switch to CPU mode in the TUI. |
| Onboarding hangs | Check >50 GB free disk; clear browser cache; check `docker compose logs` in `upstream/`. |
| UI stuck forever on "Starting OpenRAG…" | Frontend is up but the backend died waiting for Langflow, because Langflow exited: its log shows `Username and password must be set`. Cause: `LANGFLOW_SUPERUSER` / `LANGFLOW_SUPERUSER_PASSWORD` are empty in `upstream/.env` (they ship empty in the example env). `./start.sh` now auto-generates a random password (see `langflow-credentials.txt`); manual fix: set both vars in `upstream/.env`, then `docker compose up -d --force-recreate langflow openrag-backend`. Confirm with `docker compose ps -a` (langflow + backend should be Up, not Exited). |
| UI stuck on "Starting OpenRAG…" (second cause) | All containers Up and Langflow fine, but the backend log loops `OpenSearch healthy but cluster has not reached expected node count` (attempt N/100): the backend waits for `OPENSEARCH_EXPECTED_DATA_NODE_COUNT` data nodes (default **3**, `src/config/settings.py`) while the local cluster has 1. Adding it to `upstream/.env` does **not** help — upstream's compose never passes it through (verify: `docker exec openrag-backend printenv OPENSEARCH_EXPECTED_DATA_NODE_COUNT` prints nothing). `./start.sh` now writes `upstream/docker-compose.override.yml` injecting it as `1` into `openrag-backend`; manual fix: create that override, then `docker compose up -d --force-recreate openrag-backend`. |
| OpenSearch won't start | `OPENSEARCH_PASSWORD` in `.env` doesn't meet complexity rules. Change it, then `./stop.sh --wipe` and restart (password is baked into the volume). |
| Port already in use | `lsof -i :3000` (etc.) — often a previous stack still running. `./stop.sh` in the *other* POC too. Change `FRONTEND_PORT`/`LANGFLOW_PORT` in `.env` if you must (and `LANGFLOW_PUBLIC_URL` with it). |
| Langflow asks for login | Superuser credentials are the `LANGFLOW_SUPERUSER` / password values from the upstream `.env`. |
| Docling (:5001) unreachable | Docling serve is a host process in the package install and a service in compose; check `docker compose ps` and the warm-up step in upstream logs — first PDF is slow while models load. |
| Wrong/no answers, docs “complete” | Open the doc in Knowledge: are chunks sensible? Then open the Langflow ingestion flow and check chunk size/overlap and that the embedding model in the flow matches onboarding. |
