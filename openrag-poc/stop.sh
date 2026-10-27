#!/usr/bin/env bash
# Stop the OpenRAG POC.  ./stop.sh --wipe also deletes indexed data (volumes).
set -euo pipefail
cd "$(dirname "$0")/upstream" 2>/dev/null || { echo "No upstream/ checkout — nothing to stop."; exit 0; }
if [ "${1:-}" = "--wipe" ]; then
  docker compose down -v
else
  docker compose down
fi
