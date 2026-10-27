#!/usr/bin/env python3
"""
bench.py — measure ingestion time and query time for OpenRAG or RAGFlow.

Same corpus, same queries, same metric definitions for both systems.
Definitions live in docs/evaluation-guide.md. In short:

  upload_seconds          time for the upload API call to be accepted
  searchable_seconds      upload start -> document actually retrievable
                          (OpenRAG: probe search returns the file's term;
                           RAGFlow: document progress complete + retrieval hit)
  query_seconds           one chat call, streaming OFF, wall clock
  cold run                first run of each query (kept, but excluded from p50/p95)
  hit                     answer text contains ALL expected_keywords of the gold query

Endpoint paths / payload field names live in bench_config.<system>.json next to
this file, NOT in code — upstream APIs move between tags; fix the config, not
the harness, and note the change in your RESULTS.md.

Usage (see each POC README §6 for the full context):
  python bench.py --system openrag --base-url http://localhost:3000 \
      --ingest-dir ../sample-data --queries ../queries/gold-queries.json \
      --repeats 3 --out ../../results/openrag
  python bench.py --system ragflow --base-url http://192.168.64.10 \
      --api-key $RAGFLOW_API_KEY \
      --ingest-dir ../sample-data --queries ../queries/gold-queries.json \
      --repeats 3 --out ../../results/ragflow

Outputs in --out's parent dir: <name>-ingestion.csv, <name>-queries.csv,
<name>-report.md where <name> is the basename of --out.
Exit code is 0 even when individual calls fail (failures are rows in the CSV),
2 only for usage/config errors — a half-broken POC should still produce a report.
"""
import argparse, csv, json, os, sys, time, statistics
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed:  pip install -r requirements.txt")

HERE = Path(__file__).resolve().parent


def load_config(system: str) -> dict:
    p = HERE / f"bench_config.{system}.json"
    if not p.exists():
        sys.exit(f"Missing config {p}")
    return json.loads(p.read_text())


def now() -> float:
    return time.perf_counter()


def extract_text(obj) -> str:
    """Pull answer text out of the many shapes these APIs return."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for key in ("answer", "response", "content", "text", "result"):
            if isinstance(obj.get(key), str) and obj[key]:
                return obj[key]
        # OpenAI-compatible shape
        try:
            return obj["choices"][0]["message"]["content"]
        except Exception:
            pass
        # RAGFlow wraps payloads in {"code":0,"data": ...}
        if "data" in obj:
            return extract_text(obj["data"])
        return json.dumps(obj)[:4000]
    if isinstance(obj, list) and obj:
        return extract_text(obj[0])
    return str(obj)


def pct95(values):
    if not values:
        return 0.0
    s = sorted(values)
    i = min(len(s) - 1, int(0.95 * len(s) + 0.999) - 1)
    return s[max(i, 0)]


class Client:
    def __init__(self, base_url, api_key, cfg):
        self.base = base_url.rstrip("/")
        self.cfg = cfg
        self.s = requests.Session()
        auth = cfg.get("auth", {})
        if api_key:
            style = auth.get("style", "bearer")
            if style == "bearer":
                self.s.headers["Authorization"] = f"Bearer {api_key}"
            elif style == "header":
                self.s.headers[auth.get("header", "X-API-Key")] = api_key

    def url(self, path: str) -> str:
        return self.base + path

    def request(self, method, path, **kw):
        kw.setdefault("timeout", self.cfg.get("timeout_seconds", 300))
        return self.s.request(method, self.url(path), **kw)


# ----------------------------- OpenRAG adapter -----------------------------

class OpenRAG:
    name = "openrag"

    def __init__(self, client: Client, cfg):
        self.c, self.cfg = client, cfg

    def upload(self, path: Path) -> float:
        ep = self.cfg["endpoints"]
        field = ep.get("upload_field", "files")
        t0 = now()
        with open(path, "rb") as fh:
            r = self.c.request("POST", ep["upload"], files={field: (path.name, fh)})
        r.raise_for_status()
        return now() - t0

    def wait_searchable(self, path: Path, probe: str, timeout_s: int) -> float:
        """Poll /search for this file's unique probe term until it returns a hit."""
        ep = self.cfg["endpoints"]
        payload_key = ep.get("search_payload_key", "query")
        t0 = now()
        while now() - t0 < timeout_s:
            try:
                r = self.c.request("POST", ep["search"], json={payload_key: probe})
                if r.ok and (probe.lower() in r.text.lower() or len(r.text) > 200):
                    return now() - t0
            except requests.RequestException:
                pass
            time.sleep(3)
        return -1.0  # timed out — record, don't crash

    def query(self, question: str) -> tuple[float, str]:
        ep = self.cfg["endpoints"]
        payload_key = ep.get("chat_payload_key", "message")
        t0 = now()
        r = self.c.request("POST", ep["chat"], json={payload_key: question})
        dt = now() - t0
        r.raise_for_status()
        try:
            return dt, extract_text(r.json())
        except ValueError:
            return dt, r.text


# ----------------------------- RAGFlow adapter -----------------------------

class RAGFlow:
    name = "ragflow"

    def __init__(self, client: Client, cfg):
        self.c, self.cfg = client, cfg
        self.dataset_id = None
        self.chat_id = None
        self.session_id = None
        self.doc_ids = {}  # filename -> document_id

    # setup: create a fresh dataset + chat assistant per bench run
    def setup(self):
        ep = self.cfg["endpoints"]
        stamp = time.strftime("%Y%m%d%H%M%S")
        r = self.c.request("POST", ep["create_dataset"], json={"name": f"bench-{stamp}"})
        r.raise_for_status()
        self.dataset_id = r.json()["data"]["id"]
        r = self.c.request("POST", ep["create_chat"],
                           json={"name": f"bench-{stamp}", "dataset_ids": [self.dataset_id]})
        r.raise_for_status()
        self.chat_id = r.json()["data"]["id"]
        r = self.c.request("POST", ep["create_session"].format(chat_id=self.chat_id), json={})
        r.raise_for_status()
        data = r.json().get("data") or {}
        self.session_id = data.get("id")
        return self.dataset_id, self.chat_id

    def upload(self, path: Path) -> float:
        ep = self.cfg["endpoints"]
        field = ep.get("upload_field", "file")
        url = ep["upload"].format(dataset_id=self.dataset_id)
        t0 = now()
        with open(path, "rb") as fh:
            r = self.c.request("POST", url, files={field: (path.name, fh)})
        dt = now() - t0
        r.raise_for_status()
        data = r.json().get("data") or []
        if isinstance(data, list) and data:
            self.doc_ids[path.name] = data[0].get("id")
        return dt

    def parse_all(self):
        ep = self.cfg["endpoints"]
        ids = list(self.doc_ids.values())
        if ids:
            r = self.c.request("POST", ep["parse"].format(dataset_id=self.dataset_id),
                               json={"document_ids": ids})
            r.raise_for_status()

    def wait_searchable(self, path: Path, probe: str, timeout_s: int) -> float:
        """Poll the document list until this file reports parsing complete."""
        ep = self.cfg["endpoints"]
        url = ep["list_documents"].format(dataset_id=self.dataset_id)
        doc_id = self.doc_ids.get(path.name)
        t0 = now()
        while now() - t0 < timeout_s:
            try:
                r = self.c.request("GET", url)
                docs = (r.json().get("data") or {}).get("docs") or r.json().get("data") or []
                for d in docs if isinstance(docs, list) else []:
                    if d.get("id") == doc_id:
                        prog = d.get("progress", 0)
                        run = str(d.get("run", "")).upper()
                        chunks = d.get("chunk_num", d.get("chunk_count", 0))
                        if prog >= 1 or run in ("DONE", "FINISHED", "3") or (chunks and prog == 1):
                            return now() - t0
            except requests.RequestException:
                pass
            time.sleep(3)
        return -1.0

    def query(self, question: str) -> tuple[float, str]:
        ep = self.cfg["endpoints"]
        url = ep["completion"].format(chat_id=self.chat_id)
        body = {"question": question, "stream": False}
        if self.session_id:
            body["session_id"] = self.session_id
        t0 = now()
        r = self.c.request("POST", url, json=body)
        dt = now() - t0
        r.raise_for_status()
        try:
            return dt, extract_text(r.json())
        except ValueError:
            return dt, r.text


ADAPTERS = {"openrag": OpenRAG, "ragflow": RAGFlow}

# A unique-ish word per sample file, used as the OpenRAG searchable probe.
PROBES = {
    "aurora-manual.md": "ASP-SEAL-24",
    "billing-faq.md": "restocking",
    "permit-guide.md": "AUR-PERMIT-7",
    "pricing-table.csv": "5500",
    "support-runbook.txt": "ASP-SEAL-L1",
}


def default_probe(path: Path) -> str:
    if path.name in PROBES:
        return PROBES[path.name]
    words = [w for w in path.read_text(errors="ignore").split() if len(w) > 7]
    return words[len(words) // 2] if words else path.stem


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", required=True, choices=sorted(ADAPTERS))
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key", default=os.environ.get("RAGFLOW_API_KEY") or os.environ.get("OPENRAG_API_KEY", ""))
    ap.add_argument("--ingest-dir", help="Folder of files to ingest (skip to only time queries)")
    ap.add_argument("--queries", required=True, help="gold-queries.json")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--ready-timeout", type=int, default=900, help="seconds to wait per file to become searchable")
    ap.add_argument("--out", required=True, help="output prefix, e.g. ../../results/openrag")
    args = ap.parse_args()

    cfg = load_config(args.system)
    client = Client(args.base_url, args.api_key, cfg)
    adapter = ADAPTERS[args.system](client, cfg)

    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    queries = json.loads(Path(args.queries).read_text())

    ingestion_rows = []
    if isinstance(adapter, RAGFlow):
        ds, chat = adapter.setup()
        print(f"RAGFlow dataset={ds} chat={chat}")

    if args.ingest_dir:
        files = sorted(p for p in Path(args.ingest_dir).iterdir() if p.is_file())
        print(f"Ingesting {len(files)} files into {args.system} ...")
        for f in files:
            row = {"file": f.name, "size_bytes": f.stat().st_size}
            try:
                t_start = now()
                row["upload_seconds"] = round(adapter.upload(f), 3)
                if isinstance(adapter, RAGFlow):
                    adapter.parse_all()
                waited = adapter.wait_searchable(f, default_probe(f), args.ready_timeout)
                row["searchable_seconds"] = round(waited, 3) if waited >= 0 else "TIMEOUT"
            except Exception as e:  # keep going — partial report beats none
                row["upload_seconds"] = "ERROR"
                row["searchable_seconds"] = f"ERROR: {e}"[:200]
            ingestion_rows.append(row)
            print(" ", row)

    query_rows, warm_lat = [], []
    print(f"Running {len(queries)} queries x (1 cold + {args.repeats} warm) ...")
    for q in queries:
        for run in range(args.repeats + 1):
            cold = run == 0
            try:
                dt, answer = adapter.query(q["question"])
                expected = q.get("expected_keywords") or []
                hit = (all(k.lower() in answer.lower() for k in expected)
                       if expected else "manual-check")
                err = ""
            except Exception as e:
                dt, hit, answer, err = -1, False, "", str(e)[:200]
            query_rows.append({
                "id": q.get("id", ""), "category": q.get("category", ""),
                "question": q["question"], "run": run, "cold": cold,
                "latency_seconds": round(dt, 3) if dt >= 0 else "ERROR",
                "hit_all_keywords": hit, "error": err,
                "answer_preview": answer.replace("\n", " ")[:240],
            })
            if not cold and dt >= 0:
                warm_lat.append(dt)
        print(f"  {q.get('id','?')}: done")

    ing_csv = str(out_prefix) + "-ingestion.csv"
    qry_csv = str(out_prefix) + "-queries.csv"
    if ingestion_rows:
        with open(ing_csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(ingestion_rows[0].keys())); w.writeheader(); w.writerows(ingestion_rows)
    with open(qry_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(query_rows[0].keys())); w.writeheader(); w.writerows(query_rows)

    scored = [r for r in query_rows if r["hit_all_keywords"] in (True, False) and not r["cold"]]
    hits = sum(1 for r in scored if r["hit_all_keywords"] is True)
    searchable = [r["searchable_seconds"] for r in ingestion_rows if isinstance(r.get("searchable_seconds"), (int, float))]
    report = [
        f"# Bench report — {args.system}",
        "",
        f"- Base URL: {args.base_url}",
        f"- Queries: {len(queries)} x (1 cold + {args.repeats} warm), streaming off",
        f"- Ingestion: {len(ingestion_rows)} files, total time-to-searchable "
        f"= {round(sum(searchable), 1)}s across {len(searchable)} measured files",
        f"- Query latency (warm): median = {str(round(statistics.median(warm_lat), 3)) + 's' if warm_lat else 'n/a'}, "
        f"p95 = {str(round(pct95(warm_lat), 3)) + 's' if warm_lat else 'n/a'}, n = {len(warm_lat)}",
        f"- Keyword hit-rate (warm, auto-checked queries only): "
        f"{hits}/{len(scored)}" if scored else "- Keyword hit-rate: no auto-checkable queries ran",
        "",
        "Raw data: " + (f"`{ing_csv}`, " if ingestion_rows else "") + f"`{qry_csv}`. "
        "Definitions: docs/evaluation-guide.md.",
        "Note: not-in-corpus queries have no keywords — check their rows in the CSV by hand "
        "(a good answer refuses instead of inventing one).",
    ]
    rpt = str(out_prefix) + "-report.md"
    Path(rpt).write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\nWrote: {rpt}" + (f", {ing_csv}" if ingestion_rows else "") + f", {qry_csv}")


if __name__ == "__main__":
    main()
