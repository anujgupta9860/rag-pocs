# OpenRAG on a GCP VM — deployment notes (innovation-lab-2026)

Live deployment built 2026-11-02: OpenRAG **v0.3.0** on a single Compute
Engine VM (`openrag-1`, e2-standard-4, Ubuntu 24.04, us-central1-a),
OpenAI-only providers (chat `gpt-4o-mini`, embeddings
`text-embedding-3-small`). UI on port 3000, Langflow on 7860.

This folder captures everything that had to be fixed on top of upstream —
upstream v0.3.0 does **not** work out of the box in this shape.

## Fixes applied (all in `docker-compose.override.yml` unless noted)

1. **Single-node OpenSearch.** Upstream expects a multi-node cluster.
   The override sets the expected data/manager/coordinating counts to
   1/1/0 and disables the node-count check on `openrag-backend`.
   Also: `chown -R 1000:1000 opensearch-data` before first start, or the
   data node refuses to boot (root-created directory).

2. **Docling reachability — BOTH containers need the host mapping.**
   Docling runs on the host (see below); containers reach it via
   `DOCLING_SERVE_URL=http://host.docker.internal:5001` (upstream default).
   On Linux Docker, `host.docker.internal` does not resolve unless each
   service gets `extra_hosts: ["host.docker.internal:host-gateway"]`.
   Ingestion has two docling hops: the backend converts first, then the
   Langflow ingestion flow calls docling again — if only the backend has
   the mapping, uploads fail with "Ingestion service was temporarily
   unavailable" and `[Errno -2] Name or service not known` in the Langflow
   run. Both `openrag-backend` and `langflow` need it.

3. **Chat broken with the OpenAI provider — upstream bug.**
   `agent-include-fix.patch`: the backend's `src/agent.py` sends
   `include: ["tool-call.results"]` on every OpenAI Responses API call;
   the public API rejects it (400), the backend 500s `/nudges` and
   `/chat`. Patched file is bind-mounted read-only over
   `/app/src/agent.py` (pristine copy kept at `/opt/openrag/agent.py.orig`
   on the VM). Remove the volume to revert.

4. **Current-generation flows.** The v0.3.0 tagged flows mismatch the
   `:latest` backend image (0.8.1). Copy the four flows from upstream
   `main` (`flows/`: ingestion, agent, nudges, URL MCP) over the checkout's
   `flows/` before first `docker compose up`.

## Docling (not in any upstream compose file)

```bash
tmux new-session -d -s docling \
  "uv run --with docling-serve docling-serve run --host 0.0.0.0 --port 5001"
curl http://localhost:5001/health   # 200
```

Caveat: the tmux session survives SSH disconnects but **not a VM reboot** —
restart it after any reboot. Containers recover on their own.

## Operations notes

- **Onboarding** is API-only: `POST /api/onboarding` with the provider
  config; provider health at `GET /api/provider/health`.
- **Langflow superuser password**: the CLI
  (`langflow reset-password`) silently no-ops for an existing user even
  with `LANGFLOW_ENABLE_SUPERUSER_CLI=true`. What works is the
  authenticated `PATCH /api/v1/users/{id}/reset-password`. Credentials
  live on the VM in `/opt/openrag/langflow-credentials.txt` (chmod 600) —
  never in this repo.
- **Resource use** (steady state): backend ~0.4 GB, Langflow ~1.1 GB,
  OpenSearch ~1.7 GB, dashboards ~0.2 GB, frontend ~0.1 GB RAM.
- **Cost**: the VM is ≈ $108/month if left running 24/7 (disk alone
  ≈ $10/month stopped).

## Evaluation findings for the POC report

- Chat is broken out-of-the-box with the OpenAI provider (fix 3) — the
  `include` value looks written against a non-public gateway dialect.
- No self-serve user signup exists upstream: auth routes are OIDC-style
  (`/auth/init`, `/auth/callback`, `/auth/jwks`, `/users/me/permissions`)
  plus an IBM login. Hosting for end users needs an external IdP in front.
- Retrieval is hard-wired to OpenSearch; Vertex AI Search is not a
  supported index in v0.3.0 (integration would be custom work).
