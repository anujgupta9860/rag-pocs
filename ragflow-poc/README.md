# POC 2 — RAGFlow, running locally (in a Linux VM on your Mac)

**What:** [RAGFlow](https://github.com/infiniflow/ragflow) (InfiniFlow) —
DeepDoc parsing, template chunking, hybrid retrieval + reranking,
Elasticsearch/Infinity index, chat assistants and an agent canvas.
**Where:** inside an **Ubuntu ARM64 VM (UTM) on your Mac** — see
[`../docs/local-mac-and-utm.md`](../docs/local-mac-and-utm.md) for the one-time VM setup.
**Time:** ~45–90 min first run inside the VM, ~10 min after that.

> **Why a VM?** For the 1.0 line upstream states: Linux x86-64 and Linux
> ARM64 are supported, *macOS is not currently supported by the Go backend —
> use a Linux host.* The VM is that Linux host, on your own machine.
> An older 0.2x stack can be forced onto macOS Docker (`docker-compose-macos.yml`,
> Elasticsearch under `platform: linux/amd64` emulation, frequent SIGILL
> crashes, community reports only). It is **not** the path documented here:
> a POC should judge RAGFlow's parsing, not Rosetta emulation.

Upstream is **not vendored**. `start.sh` (run *inside the VM*) clones it at a
pinned tag into `./upstream/` and runs its `docker/` compose stack.

---

## 1. Prerequisites (inside the Ubuntu VM)

- Ubuntu 24.04 ARM64 VM: **4 vCPU, 8–16 GB RAM, 64 GB disk**
  (RAGFlow's documented floor is 4 cores / 16 GB RAM / 50 GB disk for the host;
  in a VM give it as much RAM as your Mac allows — see the Mac doc).
- Docker Engine + Compose plugin installed (steps in the Mac/UTM doc),
  `docker version && docker compose version` both work without sudo.
- **≥ 50 GB free** in the VM: `df -h /`
- The same LLM + embedding provider key you used for OpenRAG.
- This repo available in the VM: `git clone <this-repo>` inside the VM, or use
  UTM's shared folder. (Cloning inside the VM is simpler.)

## 2. Configure

```bash
cd ragflow-poc
cp .env.example .env     # only holds POC-level choices; upstream has its own docker/.env
```

Most RAGFlow knobs live in **upstream's `docker/.env`** after cloning:
document engine (`DOC_ENGINE=elasticsearch` default, or `infinity`),
ports (`SVR_WEB_HTTP_PORT` — 80 by default), image tag, and default passwords.
`start.sh` prints anything you must change there before first login.

**Security defaults to fix even for a laptop POC if it stays up:**
default stack passwords are publicly known (e.g. `infini_rag_flow`) and the
compose file publishes Elasticsearch/MySQL/MinIO/Redis ports. Inside a VM on
a private UTM network this is contained — do not port-forward the VM to a LAN
without changing passwords and binding those ports to 127.0.0.1 first.
Set `REGISTER_ENABLED=0` in `docker/.env` after creating your account.

## 3. Run it (inside the VM)

```bash
./start.sh
```

What it does:

1. Sets `vm.max_map_count=262144` (required by Elasticsearch; skipped if you
   set `DOC_ENGINE=infinity`).
2. Clones `infiniflow/ragflow` into `./upstream/`, checks out `$RAGFLOW_TAG`.
3. `cd upstream/docker && docker compose -f docker-compose.yml up -d`
   (CPU image profile — DeepDoc in the open-source build uses CPU inference).
4. Polls `http://localhost/api/v1/system/healthz` (1.0) until healthy, then
   prints the UI URL — `http://localhost` (default port 80, no port suffix),
   or `http://<vm-ip>` from the Mac browser.

Manual equivalent:

```bash
sudo sysctl -w vm.max_map_count=262144
git clone https://github.com/infiniflow/ragflow.git upstream
cd upstream && git checkout v0.27.2        # = RAGFLOW_TAG default
cd docker && docker compose -f docker-compose.yml up -d
docker ps                                  # es/minio/mysql/redis + ragflow up?
curl -f http://localhost/api/v1/system/healthz
docker logs --tail 50 ragflow-cpu          # if it is not coming up
```

First boot in the UI:

1. Open `http://<vm-ip>` → **Sign up** (first account becomes admin).
2. Click your avatar → **Model providers / Settings** → add your LLM provider
   (API key), then set the **system model settings**: chat model, **embedding
   model**, and rerank model (optional). *Same models as the OpenRAG POC.*
3. Avatar → **API** → **API Key** → generate a token. bench.py needs it:
   `export RAGFLOW_API_KEY=<token>` (treat it like a password).

Stop it (inside the VM):

```bash
./stop.sh            # docker compose down (data kept in volumes)
./stop.sh --wipe     # docker compose down -v (datasets + index deleted)
```

## 4. Ingest files

Key terms: a **Dataset** is the knowledge base. Uploading a file does **not**
parse it — parsing is a separate, explicit step. That separation is exactly
what you are measuring in §6.

### 4a. UI (do this first, once, by hand)

1. **Datasets → Create dataset**: name `poc-aurora`, choose the **embedding
   model** (locked per dataset once chunks exist), embedding/parse type:
   **Built-in**.
2. Open the dataset → **Configuration**: pick the chunking **template**
   for this corpus: `General` for the mixed sample set (try `Manual`/`Table`
   later on single-type datasets — per-template behaviour is a POC finding).
   Note the template name for RESULTS.md.
3. **Files → Add file → Upload file**: select all of
   `../common/sample-data/*`, enable **Parse on creation** if offered.
4. If parsing didn't auto-start: select the files → **Run**.
5. Parsing is done when each file shows **chunk count > 0** and progress
   complete. Open a file → inspect the chunks visually on the page; fix or
   delete an obviously wrong chunk once, just to learn the intervention loop.

### 4b. API (what bench.py automates — `/api/v1`)

```bash
export RAGFLOW_API_KEY=<token>     # Authorization: Bearer <token>

# 1. Create a dataset
curl -X POST http://<vm-ip>/api/v1/datasets \
  -H "Authorization: Bearer $RAGFLOW_API_KEY" -H "Content-Type: application/json" \
  -d '{"name": "poc-aurora"}'        # -> note data.id

# 2. Upload documents to it
curl -X POST http://<vm-ip>/api/v1/datasets/<dataset_id>/documents \
  -H "Authorization: Bearer $RAGFLOW_API_KEY" \
  -F "file=@../common/sample-data/permit-guide.md"

# 3. Trigger parsing into chunks
curl -X POST http://<vm-ip>/api/v1/datasets/<dataset_id>/chunks \
  -H "Authorization: Bearer $RAGFLOW_API_KEY" -H "Content-Type: application/json" \
  -d '{"document_ids": ["<document_id>"]}'

# 4. Poll parsing progress (run / progress fields per document)
curl "http://<vm-ip>/api/v1/datasets/<dataset_id>/documents" \
  -H "Authorization: Bearer $RAGFLOW_API_KEY"
```

### 4c. Retrieval test before chat (do not skip)

Dataset → **Retrieval testing**: paste a gold question, set similarity
threshold (~0.2), keyword/vector weight, top-K. This screen shows the actual
chunks and scores *without* the LLM — it separates retrieval problems from
generation problems. Save a screenshot of one good and one bad result.

## 5. Test a query

### 5a. UI — create a Chat Assistant first

A dataset alone doesn't chat. **Chat → Create assistant**: name it, attach
dataset `poc-aurora`, set the prompt (leave default for the POC), save.
Ask the 3 smoke queries, then the 12 gold queries. Check the citations open
the expected document.

### 5b. API — sessions + completions

```bash
# Create the assistant via API (or reuse the UI one: GET /api/v1/chats)
curl -X POST http://<vm-ip>/api/v1/chats \
  -H "Authorization: Bearer $RAGFLOW_API_KEY" -H "Content-Type: application/json" \
  -d '{"name": "poc-assistant", "dataset_ids": ["<dataset_id>"]}'

# Create a session, then ask (stream must be false for timing)
curl -X POST http://<vm-ip>/api/v1/chats/<chat_id>/sessions \
  -H "Authorization: Bearer $RAGFLOW_API_KEY" -H "Content-Type: application/json" -d '{}'
curl -X POST http://<vm-ip>/api/v1/chats/<chat_id>/completions \
  -H "Authorization: Bearer $RAGFLOW_API_KEY" -H "Content-Type: application/json" \
  -d '{"question": "How close to a property line can an Aurora pump be installed?", "stream": false}'

# Retrieval only (no LLM) — for retrieval-only latency in the eval guide:
curl -X POST http://<vm-ip>/api/v1/retrieval \
  -H "Authorization: Bearer $RAGFLOW_API_KEY" -H "Content-Type: application/json" \
  -d '{"question": "annual plan price Pro 3000", "dataset_ids": ["<dataset_id>"], "top_k": 8}'
```

There is also an **OpenAI-compatible** endpoint (point an OpenAI client at the
instance with your token) and an **MCP server** mode — for the agent-integration
test, start RAGFlow with its MCP server enabled per upstream docs and call it
from your MCP client; record setup time the same way as OpenRAG §5c.

### 5c. Agent Canvas (evaluate, don't adopt blindly)

**Agent → Create** from a template (e.g. a retrieval Q&A template): note how
Retrieval / Generate / Categorize / Switch / Code components compose.
For an architecture where a router already makes decisions, the POC question
is whether Canvas would *duplicate* that router — write your answer in RESULTS.md.

## 6. Measure ingestion time and query time

Definitions: [`../docs/evaluation-guide.md`](../docs/evaluation-guide.md).
For RAGFlow, **time to searchable** = upload start → document list shows
parsing complete (progress finished, chunk count > 0), confirmed by one
retrieval call. bench.py polls exactly that.

```bash
# Run on the Mac OR in the VM — it only needs HTTP access to the VM IP.
pip install -r ../common/bench/requirements.txt
export RAGFLOW_API_KEY=<token>
python ../common/bench/bench.py --system ragflow \
  --base-url http://<vm-ip> \
  --api-key "$RAGFLOW_API_KEY" \
  --ingest-dir ../common/sample-data \
  --queries ../common/queries/gold-queries.json \
  --repeats 3 --out ../results/ragflow
# bench.py creates a fresh dataset + assistant itself (names are timestamped),
# uploads, triggers parsing, polls to completion, then times the queries.
# -> ../results/ragflow-ingestion.csv, -queries.csv, -report.md
```

Clean run: `./stop.sh --wipe && ./start.sh` is *not* required — a fresh
dataset per bench run is enough (that's why bench.py creates one).

Manual stopwatch method (VM shell):

```bash
for i in 1 2 3; do
  /usr/bin/time -f "%e s" curl -s -X POST http://localhost/api/v1/chats/<chat_id>/completions \
    -H "Authorization: Bearer $RAGFLOW_API_KEY" -H "Content-Type: application/json" \
    -d '{"question": "What does the Pro 3000 cost per year on the annual plan?", "stream": false}' \
    -o /dev/null
done
```

## 7. What to record for the comparison

- Setup time (VM already built → first answer), ingestion per file, query p50/p95
- **Parsing quality**: open the pricing table and the permit guide chunks —
  are table rows/cells intact? Values exact?
- Retrieval-test findings (§4c): threshold/weight changes that fixed a miss
- One chunking-template experiment: re-parse one dataset with a different
  template, re-run its queries — effort + effect
- Canvas overlap note (§5c) and MCP/REST integration effort

## 8. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Elasticsearch container exits / OOM | `vm.max_map_count` < 262144 in the **VM** (not on the Mac): `sudo sysctl -w vm.max_map_count=262144` and persist it in `/etc/sysctl.conf`. Or give the VM more RAM. Or switch `DOC_ENGINE=infinity` in upstream `docker/.env`. |
| Stack up, UI blank/502 | First boot/migrations still running: `docker logs --tail 100 ragflow-cpu`; wait, then hard-refresh. Check all dependency containers are healthy in `docker ps`. |
| Can't reach UI from Mac | Use the VM's IP (`ip a` inside VM, UTM Shared Network = `192.168.64.x`), not `localhost` on the Mac. Check the web port in upstream `docker/.env` (`SVR_WEB_HTTP_PORT`). |
| File uploads but never parses | You skipped the parse step (§4): select file → **Run**, or POST to `/chunks`. Check the file's **Logs** and `docker logs ragflow-cpu` for the task executor. |
| Parsing extremely slow | Normal on CPU for scanned/table docs (DeepDoc does layout+OCR+TSR on CPU). This is a *measurement*, record it — don't “fix” it mid-POC. Reduce corpus, not settings. |
| “Embedding model” errors on dataset | All docs in a dataset share one embedding model; if chunks exist you cannot freely swap it. Create a fresh dataset with the right model instead. |
| Answers ignore the docs | Use Retrieval testing (§4c) first: if chunks aren't retrieved, it's threshold/weight/top-K or chunking — not the LLM prompt. |
| It worked on an older tag, API differs now | Endpoints live in `../common/bench/bench_config.ragflow.json` — check the tag's API docs at ragflow.io/docs, adjust paths there, note it in RESULTS.md. |
