# Concepts — everything in OpenRAG and RAGFlow, in plain English

## RAG in one paragraph

Retrieval-Augmented Generation: the LLM does not memorise your documents.
At question time the system **retrieves** the most relevant passages from your
corpus and pastes them into the prompt; the LLM answers *from those passages*
and cites them. Quality is decided long before the LLM speaks — by parsing,
chunking and retrieval.

## The shared pipeline (both systems implement this)

| Stage | What happens | Failure mode if done badly |
|---|---|---|
| **Corpus / Knowledge base / Dataset** | Your collection of documents. “Knowledge” in OpenRAG, “Dataset” in RAGFlow. | Mixing unrelated domains pollutes retrieval. |
| **Ingestion** | Upload / crawl / sync files into the system. | Silent failures; unsupported formats dropped. |
| **Parsing** | Extract text *with structure*: headings, reading order, tables, figures, OCR for scans. | Garbage in — tables become word salad, retrieval can never recover. |
| **Chunking** | Split the parsed document into retrievable pieces, ideally on semantic boundaries. | Too big = noisy context; too small = answers lose their context. |
| **Embedding** | Each chunk → a vector via an embedding model. Meaning becomes geometry. | Wrong/weak model = “similar” chunks are not actually similar. One dataset = one embedding model (RAGFlow enforces this). |
| **Index** | Chunks + vectors + full-text index in a search engine (OpenSearch / Elasticsearch / Infinity). | — |
| **Retrieval** | Find candidate chunks for a query: **dense/vector** search (meaning), **keyword/BM25** search (exact words, codes, names), **hybrid** = both, weighted. | Vector-only misses exact terms (permit numbers); keyword-only misses paraphrases. |
| **Reranking** | A slower, more accurate model re-orders the top ~30–50 candidates to a top ~5–8. | Without it, the *right* chunk is retrieved but buried at #27. |
| **Generation** | Prompt = instruction + retrieved chunks + question → LLM answer. | LLM improvises when chunks are weak — see “grounding”. |
| **Grounded citations** | Every claim points back to chunk/page/document. | Unverifiable answers; hallucinations pass as fact. |
| **Agentic RAG** | Loop instead of one pass: decompose the question → retrieve → check evidence → retrieve again / call tools → answer. | Overkill (slow, costly) for simple lookups. |
| **Evaluation** | Gold questions with known-correct sources; measure hit-rate, groundedness, latency. | “It feels good in the demo” is not a result. |

Advanced terms you will meet:

- **GraphRAG** (RAGFlow): build an entity–relation graph over the corpus;
  multi-hop questions (“who approved the thing that depends on X?”) traverse it.
- **RAPTOR** (RAGFlow): recursively summarise chunks into a tree, so broad
  “summarise the theme” questions retrieve summaries, not just needles.
- **Knowledge Compilation** (RAGFlow, newer): compile a dataset into Wikis,
  graphs, trees, mind-maps, timelines or skills for reuse.
- **MCP (Model Context Protocol)**: a standard way for an AI tool/agent to call
  an external tool. Both systems expose their knowledge base over MCP, so an
  agent framework can use them as a *retrieval skill* instead of their chat UI.
- **Nudges** (OpenRAG): generated follow-up questions after an answer.

## OpenRAG — a pre-wired stack of three best-of-breed parts

`github.com/langflow-ai/openrag` · site openr.ag · Apache-2.0 · FastAPI + Next.js

- **Docling (IBM)** — the parser. Layout-aware; extracts tables/figures/structure
  from PDF, Word, PowerPoint, Excel, HTML, images and scans. Runs as a service
  on port **5001**, on the host under macOS so it can use Apple Silicon.
- **OpenSearch** — the index. Hybrid search (kNN vector + BM25). One index can
  hold embeddings from *several* models at once in fields named
  `chunk_embedding_<model>` — handy when migrating embedding models.
- **Langflow** — the orchestrator. The whole pipeline is editable visual
  **flows** (JSON graphs): *Ingestion flow*, *URL-ingestion flow*, *Chat/Agent
  flow*, *Nudges flow*. If retrieval misbehaves, you open the flow and look.
- Services/ports: UI **3000**, backend API **8000**, Langflow **7860**,
  OpenSearch **9200**, OpenSearch Dashboards **5601**, Docling **5001**.
- Access: **Basic (no-auth)** = everyone sees all documents.
  **Advanced (OAuth)** = per-user/group document access. Decide at setup time.
- Integration: REST API, Python + TypeScript SDKs, and a built-in **MCP server
  at `/mcp`** (auth: `X-API-Key` header) for Cursor / Claude Desktop / agents.
- Character: younger and simpler. Fewer chunking knobs; customisation lives
  inside Langflow flows.

## RAGFlow — a RAG *engine* whose bet is document understanding

`github.com/infiniflow/ragflow` · Apache-2.0 · historically Python, 1.0 line adds a Go server

- **DeepDoc** — its own parser: OCR + layout recognition (titles, text, tables,
  figures, headers/footers…) + **Table Structure Recognition** (rows, columns,
  merged cells). Optimised for scanned, multi-column, table-heavy documents.
- **Template-based chunking** — choose per dataset: General, Q&A, Manual,
  Table, Paper, Book, Laws, Presentation, Resume, Picture, One, Tag…
  Chunks are shown **visually on the page** and can be hand-corrected.
- **Dataset** = knowledge base. One embedding model per dataset; changing it
  means re-embedding. Files in MinIO, metadata in MySQL, async parsing via a
  Redis task queue, index in **Elasticsearch** (default) or **Infinity**
  (InfiniFlow's own engine) or OpenSearch.
- **Retrieval** — multiple recall paths + **fused reranking**; a *Retrieval
  Test* screen lets you tune similarity threshold, keyword/vector weight,
  top-K and reranker *before* wiring up chat. Defaults commonly cited:
  keyword weight 0.7, similarity threshold 0.2.
- **Chat Assistant** — a separate object bound to one or more datasets
  (prompt, model, citation settings). Dataset ≠ assistant: don't confuse them.
- **Agent Canvas** — visual workflows (Begin, Retrieval, Generate, Categorize,
  Switch, Iteration, sandboxed Code, HTTP, MCP, sub-agents) plus prebuilt
  templates. Newer releases: Agentic RAG thinking modes (Low/Medium/High/Ultra).
- Integration: REST (`/api/v1/...`), Python SDK, MCP server, and an
  **OpenAI-compatible** chat endpoint — anything that speaks OpenAI can point at it.
- Character: mature, powerful, heavy. Minimum ~**4 CPU / 16 GB RAM / 50 GB disk**.
  Parsing quality is the headline; the agent canvas overlaps with external
  agent frameworks, so for an agent POC use it *retrieval-first*.

## The one-slide difference

> **OpenRAG assembles** three excellent external components into one package
> and makes customisation a Langflow-flow problem.
> **RAGFlow builds** its own deep parser and retrieval workbench and makes
> quality a chunking/tuning problem.
> POC question: on *your* documents, which bet pays?
