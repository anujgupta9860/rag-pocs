# POC Results — OpenRAG vs RAGFlow

Copy this file to `results/RESULTS.md` and fill it in. Attach the bench CSVs.

## Setup (must be identical or the comparison is void)

| Item | OpenRAG | RAGFlow |
|---|---|---|
| Version / tag | | |
| Where it ran | macOS Docker | Ubuntu ARM64 VM (UTM) on same Mac |
| Machine / RAM allocated | | |
| Document engine | OpenSearch | Elasticsearch / Infinity |
| Chat model + provider | | |
| Embedding model | | |
| Reranker | | |
| Chunking setting | flow default | template: ______ |
| Corpus | common/sample-data (5 files) + ______ real docs | same |
| Setup time (install → first answer) | | |

## Ingestion (from bench.py report — cold, empty KB, file by file)

| File | Size | OpenRAG upload s | OpenRAG searchable s | RAGFlow upload s | RAGFlow searchable s |
|---|---|---|---|---|---|
| aurora-manual.md | | | | | |
| billing-faq.md | | | | | |
| permit-guide.md | | | | | |
| pricing-table.csv | | | | | |
| support-runbook.txt | | | | | |
| **Total** | | | | | |

## Query time (gold queries, 3 warm runs each, streaming off)

| Metric | OpenRAG | RAGFlow |
|---|---|---|
| Median (p50) latency | | |
| p95 latency | | |
| Retrieval-only median (search API) | | |
| Cold first-query latency | | |

## Quality (12 gold queries)

| Check | OpenRAG | RAGFlow |
|---|---|---|
| Keyword hit-rate (bench.py) | /12 | /12 |
| Citations actually support the answer (spot-check 5) | /5 | /5 |
| Table question — values correct? | | |
| Scan/permit question — correct? | | |
| “Not in corpus” questions — refused cleanly? | /2 | /2 |
| Worst wrong answer (quote it) | | |

## Effort, integration, ops

| Item | OpenRAG | RAGFlow |
|---|---|---|
| Called via REST from outside UI? (what it took) | | |
| Called via MCP? (what it took) | | |
| Time to fix one wrong answer (tuning) | | |
| Idle RAM / during ingestion (`docker stats`) | | |
| What broke + fix | | |

## Recommendation

- Winner for document-heavy / table / scan corpus:
- Winner for agent integration (as a skill behind a router):
- Winner for operational simplicity on a laptop / small team:
- **Overall pick + one-paragraph why:**
- What would change this decision at production scale:
