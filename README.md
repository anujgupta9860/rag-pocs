# RAG POCs — OpenRAG vs RAGFlow, running locally on a Mac

Two proof-of-concepts for the same job, on the **same corpus, with the same
questions, measured the same way** — so the comparison means something.

| POC | What it is | Runs locally on macOS? |
|---|---|---|
| [`openrag-poc/`](openrag-poc/) | [OpenRAG](https://github.com/langflow-ai/openrag) (openr.ag) — IBM/Langflow: **Docling** (parsing) + **OpenSearch** (hybrid search) + **Langflow** (flows) | **Yes, directly.** Docker/Podman on macOS, Docling runs on the host and can use Apple Silicon (MLX). |
| [`ragflow-poc/`](ragflow-poc/) | [RAGFlow](https://github.com/infiniflow/ragflow) — InfiniFlow: **DeepDoc** (parsing) + template chunking + **Elasticsearch/Infinity**, agent canvas | **Not directly on macOS for v1.0** (Go backend: “use a Linux host”). Runs locally in an **Ubuntu ARM64 VM (UTM)** on the same Mac. Older 0.2x on macOS Docker is an unsupported workaround — see `ragflow-poc/README.md`. |

Both are Apache-2.0, self-hosted, and bring-your-own LLM/embedding model.
For a fair POC, **use the same chat model and the same embedding model in both**
(e.g. one cloud provider, or one local Ollama) — otherwise you are benchmarking
models, not RAG systems.

## Repo map

```
.
├── README.md                  <- you are here
├── docs/
│   ├── concepts.md            <- every concept in both systems, plain English
│   ├── comprehensive-guide.md <- the deep document: internals, 14-dimension comparison, decision framework
│   ├── evaluation-guide.md    <- HOW to measure: ingestion time, query time, quality
│   ├── local-mac-and-utm.md   <- Mac setup: Docker Desktop settings + UTM Ubuntu VM for RAGFlow
│   └── results-template.md    <- fill-in score sheet to send back / present
├── common/
│   ├── sample-data/           <- the shared test corpus (5 docs: manual, FAQ, permit guide, pricing table, runbook)
│   ├── queries/
│   │   ├── gold-queries.json  <- 12 questions with expected doc + expected keywords
│   │   └── smoke-queries.txt  <- 3 one-liners for a first sanity check
│   ├── bench/
│   │   ├── bench.py           <- measures ingestion time + query time for EITHER system
│   │   ├── bench_config.openrag.json
│   │   ├── bench_config.ragflow.json
│   │   └── requirements.txt
│   └── scripts/check-local.sh <- pre-flight: Docker, RAM, disk, free ports
├── openrag-poc/
│   ├── README.md              <- run / ingest / query / measure, step by step
│   ├── .env.example
│   ├── start.sh  / stop.sh
│   └── (upstream OpenRAG is cloned into ./upstream/ by start.sh — not vendored)
├── ragflow-poc/
│   ├── README.md              <- run INSIDE the Ubuntu VM / ingest / query / measure
│   ├── .env.example
│   ├── start.sh  / stop.sh    <- run these inside the VM
│   └── (upstream RAGFlow is cloned into ./upstream/ by start.sh — not vendored)
└── results/                   <- bench.py writes CSV/JSON/Markdown reports here
```

Why wrappers and not vendored copies? The POC should test the *real upstream
projects at a pinned tag*, not a fork that drifts. `start.sh` clones upstream,
checks out the pinned tag, and starts it. Change one variable to try a newer tag.

## Quick start (the short version — full steps in each POC's README)

### 0. Pre-flight (both)

```bash
bash common/scripts/check-local.sh
# Needs: Docker Desktop (OpenRAG) running, >=50 GB free disk,
# ports 3000 8000 7860 9200 5601 5001 free for OpenRAG,
# and a UTM Ubuntu VM (see docs/local-mac-and-utm.md) for RAGFlow.
```

### 1. OpenRAG (on macOS, ~30–60 min first time — image pulls dominate)

```bash
cd openrag-poc
cp .env.example .env   # fill in ONE llm + embedding provider key
./start.sh             # clones upstream, docker compose up, waits for health
# Open http://localhost:3000 -> sign up/in -> Knowledge -> upload ../common/sample-data/*
# Chat -> ask the smoke queries in ../common/queries/smoke-queries.txt
```

### 2. RAGFlow (inside the Ubuntu ARM64 VM, ~45–90 min first time)

```bash
# On the Mac: create the VM once — docs/local-mac-and-utm.md
# Inside the VM:
cd ragflow-poc
./start.sh             # clones upstream, sets vm.max_map_count, docker compose up -d
# Open http://localhost (in the VM browser, or the VM's IP from the Mac)
# -> register -> Settings: add the SAME model provider as OpenRAG
# -> Datasets -> Create dataset -> upload ../../common/sample-data/* -> Run (parse)
# -> Chat -> Create assistant on that dataset -> ask the same smoke queries
```

**Do not run both stacks at the same time on a 16 GB Mac.** OpenRAG wants
~8 GB for its containers and RAGFlow wants ~16 GB inside its VM. Run one,
measure it, stop it (`./stop.sh`), then run the other.

### 3. Measure both the same way

```bash
pip install -r common/bench/requirements.txt

# Ingestion time (upload -> searchable) + query time (per gold query, x3 runs)
python common/bench/bench.py --system openrag --ingest-dir common/sample-data \
    --queries common/queries/gold-queries.json --out results/openrag

python common/bench/bench.py --system ragflow --ingest-dir common/sample-data \
    --queries common/queries/gold-queries.json --out results/ragflow
# (RAGFlow: pass --api-key, and either --dataset-id + --chat-id from the UI,
#  or let bench.py create them — see ragflow-poc/README.md §5)
```

Each run writes `results/<name>-ingestion.csv`, `results/<name>-queries.csv`
and `results/<name>-report.md` with median / p95 query time, ingestion time per
file and in total, and a keyword hit-rate against the gold answers.
Definitions of every metric are in [`docs/evaluation-guide.md`](docs/evaluation-guide.md).

### 4. Score and decide

Copy [`docs/results-template.md`](docs/results-template.md) to `results/RESULTS.md`,
fill it from the two reports + your notes on parsing quality (tables/scans) and
integration effort, and that file *is* the POC deliverable.

## What a good POC answers

1. **Parsing:** which system survives a table, a scanned page and a messy PDF?
2. **Retrieval:** for the 12 gold queries, is the right chunk in the answer's citations?
3. **Speed:** ingestion time per document, and query latency (median + p95, warm).
4. **Integration:** how hard is it to call as a *skill/tool* (MCP / REST) from an
   agent framework, instead of using its own chat UI? Both ship an MCP server
   and a REST API — test that path, not only the UI.
5. **Ops:** setup time, resource use, what broke, and how you fixed it.

## Pinned upstream versions

| System | Repo | Pinned tag in start.sh | Licence |
|---|---|---|---|
| OpenRAG | github.com/langflow-ai/openrag | `v0.3.0` (change `OPENRAG_TAG`) | Apache-2.0 |
| RAGFlow | github.com/infiniflow/ragflow | `v0.27.2` stable line for the VM build; v1.0.0-rc line documented in its README (change `RAGFLOW_TAG`) | Apache-2.0 |

> Version note: upstream moves fast. If a tag is missing when you clone, pick
> the newest *stable* (non-`rc`) tag with `git tag | sort -V | tail -20` and put
> it in the `.env`. The bench harness talks to documented REST endpoints and
> tells you what to adjust if an endpoint moved (see each POC README § API notes).

## Safety / hygiene

- `.env` files hold API keys — they are git-ignored. Never commit a filled `.env`.
- Both stacks publish database/search ports locally by default. This is a
  **laptop POC**: do not expose it to a LAN/internet, and change default
  passwords if you keep it running (RAGFlow's stack defaults are public).
- Sample data in `common/sample-data/` is fictional (“Aurora Solar Pump Co.”).
  Add your real test documents alongside it, do not replace it — the gold
  queries are written against the fictional corpus.
