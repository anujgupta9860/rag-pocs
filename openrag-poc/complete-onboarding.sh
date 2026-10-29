#!/usr/bin/env bash
# Complete OpenRAG onboarding from the terminal — no UI wizard.
#
# Why this exists: onboarding state is stored server-side and gates the UI,
# so putting the provider/model/key in .env alone never clears the wizard —
# onboarding still has to be completed once. The wizard's "Complete" button
# just POSTs to /api/onboarding; this script does the same call directly.
#
# The provider and models are read from the stack's .env (upstream/.env,
# falling back to this folder's .env), so whatever is in the env is what
# gets configured. NO API key is sent in the payload: the backend uses the
# key from its own environment (e.g. OPENAI_API_KEY in .env). Make sure the
# stack was (re)started after any .env edit — env is only read when the
# containers are created (re-run start.sh, or `docker compose up -d
# --force-recreate` inside upstream/).
set -euo pipefail
cd "$(dirname "$0")"

BASE_URL="${OPENRAG_BASE_URL:-http://localhost:3000}"
ENV_FILE="upstream/.env"
[ -f "$ENV_FILE" ] || ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
  echo "No .env found (looked for upstream/.env and ./.env). Run start.sh first." >&2
  exit 1
fi

get_env() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-; }

LLM_PROVIDER="$(get_env LLM_PROVIDER)";             LLM_PROVIDER="${LLM_PROVIDER:-openai}"
LLM_MODEL="$(get_env LLM_MODEL)";                   LLM_MODEL="${LLM_MODEL:-gpt-4o-mini}"
EMBEDDING_PROVIDER="$(get_env EMBEDDING_PROVIDER)"; EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-openai}"
EMBEDDING_MODEL="$(get_env EMBEDDING_MODEL)";       EMBEDDING_MODEL="${EMBEDDING_MODEL:-text-embedding-3-small}"

# Sanity check only (prefix, never the value): with an OpenAI provider the
# backend needs a real key in its env, or onboarding fails as "invalid key".
if [ "$LLM_PROVIDER" = "openai" ] || [ "$EMBEDDING_PROVIDER" = "openai" ]; then
  case "$(get_env OPENAI_API_KEY)" in
    sk-*) : ;;
    *) echo "Warning: OPENAI_API_KEY in $ENV_FILE does not start with 'sk-' — onboarding will likely fail until the real key is in the env and the stack is recreated." >&2 ;;
  esac
fi

PAYLOAD="{\"llm_provider\":\"$LLM_PROVIDER\",\"llm_model\":\"$LLM_MODEL\",\"embedding_provider\":\"$EMBEDDING_PROVIDER\",\"embedding_model\":\"$EMBEDDING_MODEL\""
if [ "$LLM_PROVIDER" = "ollama" ] || [ "$EMBEDDING_PROVIDER" = "ollama" ]; then
  OLLAMA_ENDPOINT="$(get_env OLLAMA_ENDPOINT)"; OLLAMA_ENDPOINT="${OLLAMA_ENDPOINT:-http://host.docker.internal:11434}"
  PAYLOAD="$PAYLOAD,\"ollama_endpoint\":\"$OLLAMA_ENDPOINT\""
fi
PAYLOAD="$PAYLOAD}"

echo "Completing onboarding at $BASE_URL from $ENV_FILE:"
echo "  llm:       $LLM_PROVIDER / $LLM_MODEL"
echo "  embedding: $EMBEDDING_PROVIDER / $EMBEDDING_MODEL"
curl -sf -X POST "$BASE_URL/api/onboarding" \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD"
echo
echo "Provider health:"
curl -s "$BASE_URL/api/provider/health" || true
echo
echo "Onboarding status:"
curl -s "$BASE_URL/api/onboarding-status" || true
echo
echo "Done. Refresh $BASE_URL — the wizard should be gone."
