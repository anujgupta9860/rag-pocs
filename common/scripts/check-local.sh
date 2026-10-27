#!/usr/bin/env bash
# Pre-flight for both POCs on a Mac. Run from anywhere: bash common/scripts/check-local.sh
set -u
fail=0
echo "== Machine =="
uname -m; sysctl -n machdep.cpu.brand_string 2>/dev/null || true
echo "RAM: $(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 )) GB"
echo
echo "== Disk (need >= 60 GB free) =="
df -h / | tail -1
echo
echo "== Docker (OpenRAG, and inside the VM for RAGFlow) =="
if docker version >/dev/null 2>&1; then docker version --format 'client {{.Client.Version}} / server {{.Server.Version}}'; else echo "Docker NOT running/reachable"; fail=1; fi
docker compose version 2>/dev/null || echo "docker compose plugin missing"
echo
echo "== Ports for OpenRAG (3000 8000 7860 9200 5601 5001 must be free) =="
for p in 3000 8000 7860 9200 5601 5001; do
  if lsof -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; then echo "port $p BUSY"; else echo "port $p free"; fi
done
echo
echo "== UTM (for the RAGFlow VM) =="
[ -d /Applications/UTM.app ] && echo "UTM installed" || echo "UTM not found — brew install --cask utm (or use Parallels/VMware). See docs/local-mac-and-utm.md"
echo
[ "$fail" = 0 ] && echo "Pre-flight OK (port warnings above are informational — busy just means a stack is already running)." || echo "Pre-flight found blockers above."
