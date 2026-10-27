#!/usr/bin/env bash
# Stop the RAGFlow POC (run inside the VM). --wipe also deletes datasets/index.
set -euo pipefail
cd "$(dirname "$0")/upstream/docker" 2>/dev/null || { echo "No upstream/docker — nothing to stop."; exit 0; }
if [ "${1:-}" = "--wipe" ]; then
  docker compose -f docker-compose.yml down -v
else
  docker compose -f docker-compose.yml down
fi
