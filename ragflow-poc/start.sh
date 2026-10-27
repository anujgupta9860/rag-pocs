#!/usr/bin/env bash
# Start the RAGFlow POC — RUN THIS INSIDE THE UBUNTU VM, not on macOS.
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(uname -s)" != "Linux" ]; then
  echo "RAGFlow must run on Linux. Run this inside the UTM Ubuntu VM" >&2
  echo "(see ../docs/local-mac-and-utm.md). Refusing to start on $(uname -s)." >&2
  exit 1
fi

TAG="${RAGFLOW_TAG:-v0.27.2}"
ENGINE="${DOC_ENGINE:-elasticsearch}"
[ -f .env ] && { set -a; . ./.env; set +a; TAG="${RAGFLOW_TAG:-$TAG}"; ENGINE="${DOC_ENGINE:-$ENGINE}"; }

if [ "$ENGINE" = "elasticsearch" ]; then
  cur="$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)"
  if [ "$cur" -lt 262144 ]; then
    echo "Setting vm.max_map_count=262144 (needs sudo)..."
    sudo sysctl -w vm.max_map_count=262144
  fi
fi

if [ ! -d upstream/.git ]; then
  git clone https://github.com/infiniflow/ragflow.git upstream
fi
git -C upstream fetch --tags --quiet || true
git -C upstream checkout "$TAG"

# Respect the chosen document engine in upstream's env if the file exposes it.
if [ -f upstream/docker/.env ] && grep -q '^DOC_ENGINE=' upstream/docker/.env; then
  sed -i.bak "s/^DOC_ENGINE=.*/DOC_ENGINE=$ENGINE/" upstream/docker/.env
fi

cd upstream/docker
docker compose -f docker-compose.yml up -d
echo "Waiting for RAGFlow health endpoint..."
for i in $(seq 1 72); do
  if curl -sf -o /dev/null http://localhost/api/v1/system/healthz; then break; fi
  sleep 5
done
echo
echo "RAGFlow POC: open http://localhost in the VM, or http://<vm-ip> from the Mac"
echo "(default web port is 80 — check SVR_WEB_HTTP_PORT in upstream/docker/.env)"
echo "Next: sign up, add model providers (Settings), create a dataset, upload ../../common/sample-data/*"
