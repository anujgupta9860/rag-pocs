# bench.py — ingestion + query timing harness

Measures both POCs identically. Full metric definitions:
[`../../docs/evaluation-guide.md`](../../docs/evaluation-guide.md).

```bash
pip install -r requirements.txt
python bench.py --help
```

- Ingestion is timed **file by file**: `upload_seconds` (API accepts) and
  `searchable_seconds` (actually retrievable — the honest number).
- Queries run **1 cold + N warm** (`--repeats`, default 3). Report gives warm
  median + p95 from the CSV rows.
- RAGFlow mode creates a fresh timestamped dataset + chat assistant per run,
  uploads, triggers parsing, and polls the document list to completion.
- OpenRAG mode uploads to `/upload`, then polls `/search` with a per-file
  probe term until it hits.
- Endpoint paths/fields are in `bench_config.<system>.json`, not in code.
  If your upstream tag moved an API, bench.py fails loudly with status + body;
  fix the config, note it in RESULTS.md.
- Outputs: `<out>-ingestion.csv`, `<out>-queries.csv`, `<out>-report.md`.
- `--dry-check` is not a mode: to smoke-test the harness itself without a
  stack, point it at any URL — every row will be an ERROR row but the CSV /
  report files are still produced, which is how you verify paths and parsing.
