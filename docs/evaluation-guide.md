# Evaluation guide — how to measure ingestion time, query time, and quality

Same corpus, same questions, same models, same measurement code for both
systems — that is what makes the numbers comparable. `common/bench/bench.py`
implements everything below; this page defines the terms so the report can be
defended in a review.

## 1. Freeze the setup before measuring

Record in `results/RESULTS.md`:

- Machine (chip, total RAM), Docker Desktop / VM allocation (CPU, RAM)
- System + tag (e.g. OpenRAG v0.3.0 / RAGFlow v0.27.2), document engine
  (OpenSearch vs Elasticsearch vs Infinity)
- Chat model + provider, embedding model, reranker (or “none”)
- Chunking setting (OpenRAG: flow default / RAGFlow: template name), top-K
- Corpus: file list + sizes (`ls -lh common/sample-data/`)

Changing any of these mid-run invalidates the comparison. Re-run both sides.

## 2. Ingestion time

Two different numbers — report both, never merge them:

| Metric | Definition | How bench.py gets it |
|---|---|---|
| **Upload time** | Wall time for the upload API call(s) to be accepted, per file and total. | Timed around the HTTP upload request. |
| **Time to searchable** (the one that matters) | From upload start until the document is parsed, chunked, embedded and *actually retrievable*. | OpenRAG: poll `POST /search` for a unique probe term from the file until it returns a hit. RAGFlow: poll `GET /api/v1/datasets/{id}/documents` until every document's progress is complete, then confirm with one retrieval call. |

Rules:

- Measure on a **cold, empty** knowledge base/dataset. Delete and recreate it
  between systems, and between repeat runs.
- Ingest the corpus **file by file** (not one zip) so per-file times are visible —
  the scanned/table-heavy file is where parsers separate.
- Note file size next to each time. “3.2 s for a 4 KB .md” and “48 s for a
  40-page scanned PDF” are both plausible; without size the number is noise.
- Manual cross-check (no code): in each UI, upload one file with a stopwatch —
  OpenRAG *Knowledge* page shows processing status; RAGFlow *Dataset → Files*
  shows a progress bar / chunk count when parsing finishes. UI time should be
  within a few seconds of the script's “time to searchable”.

## 3. Query time

| Metric | Definition |
|---|---|
| **Query latency (per run)** | Wall time from sending the question to the complete answer (streaming OFF — streaming makes “total time” incomparable). |
| **Time to first token** (optional) | Only if you also test streaming; report separately. |
| **Median (p50) / p95** | Run every gold query **3× warm** (discard the first, cold, run — model/index warm-up dominates it) and report median + p95 across all warm runs. Averages hide the tail; medians don't. |
| **Retrieval-only time** | Where the API allows it (RAGFlow `POST /api/v1/retrieval`, OpenRAG `POST /search`), time search *without* generation. This separates “retrieval is slow” from “the LLM is slow” — crucial because both POCs share the same LLM. |

Rules:

- Same chat + embedding model in both systems (§1). If the LLM differs, query
  time compares LLMs, not RAG.
- No other load on the machine during query runs. Close the other stack.
- bench.py writes every run to `results/<name>-queries.csv` (query, run #,
  latency, hit/miss) — keep the CSV, don't keep only the summary.

## 4. Answer quality (on the 12 gold queries)

`common/queries/gold-queries.json`: each item has `question`, `expected_doc`,
and `expected_keywords` (words a correct answer must contain).

- **Keyword hit** (automatic, rough): answer contains all expected keywords →
  hit. bench.py computes a hit-rate %. This catches empty/wrong-doc answers,
  *not* subtle wrongness.
- **Citation check** (manual, 5 min): for 5 queries, open the cited source in
  the UI. Does the cited chunk actually support the answer, and is it from
  `expected_doc`?
- **Hallucination test** (manual): gold queries include questions whose answer
  is *not* in the corpus. Correct behaviour: “not found / I don't know” with
  no invented citation. Score pass/fail per system.
- **Table/scan check** (manual): ask the pricing-table question and the
  scanned/permit question; compare against the source values by eye. Record
  the exact wrong numbers if any — that detail wins design reviews.

## 5. The rest of the scorecard

From `docs/results-template.md`:

- Setup time (your watch, first install → first answer)
- Resource use at idle and during ingestion (`docker stats`)
- Integration: call via MCP and via REST from outside the UI; note glue code/effort
- What broke, and the fix (this is often the deciding factor)

## 6. Reproduce a run

```bash
pip install -r common/bench/requirements.txt
python common/bench/bench.py --help

# OpenRAG (stack running on http://localhost:3000, API key if you enabled one)
python common/bench/bench.py --system openrag \
  --base-url http://localhost:3000 \
  --ingest-dir common/sample-data \
  --queries common/queries/gold-queries.json \
  --repeats 3 --out results/openrag

# RAGFlow (stack running in the VM, token from Settings -> API -> API Key)
python common/bench/bench.py --system ragflow \
  --base-url http://<vm-ip> \
  --api-key <ragflow-token> \
  --ingest-dir common/sample-data \
  --queries common/queries/gold-queries.json \
  --repeats 3 --out results/ragflow
```

If an endpoint has moved in a newer upstream tag, bench.py fails with the HTTP
status and response body — check that system's API docs/OpenAPI page, adjust
`common/bench/bench_config.<system>.json` (paths and field names live there,
not in code), and note the change in RESULTS.md.
