# Running both POCs “on my local” — Mac setup

Your Mac (Apple Silicon, M4 class) runs the two systems in two different ways.
This is not a workaround preference, it is what upstream supports:

- **OpenRAG → directly on macOS** (Docker/Podman containers + Docling on host).
- **RAGFlow v1.0 → inside a Linux VM on the Mac.** Upstream: Linux x86-64 and
  Linux ARM64 are supported; “macOS is not currently supported by the Go
  backend — use a Linux host.” The VM below *is* that Linux host, and it lives
  on your Mac, offline from any cloud account.

## A. Shared Mac prep

1. **Disk:** keep **≥ 60 GB free** (`df -h /`). Images + indexes are large;
   OpenRAG's own troubleshooting asks for >50 GB free for ingestion temp space.
2. **Docker Desktop** (for OpenRAG):
   - Install/start Docker Desktop for Apple Silicon.
   - Settings → Resources: **CPUs 4, Memory 10–12 GB** (on a 16 GB Mac do not
     give Docker all of it — macOS needs headroom), Disk ≥ 60 GB.
   - Verify: `docker version && docker compose version`
3. **Ports must be free** before each stack: `bash common/scripts/check-local.sh`
   - OpenRAG: 3000, 8000, 7860, 9200, 5601, 5001
   - RAGFlow (inside VM): 80 (web), plus its internal stack ports in the VM only.
4. **One stack at a time** on a 16 GB machine. Stop one before starting the other.
5. **Models:** for the POC, point *both* systems at the same cloud LLM +
   embedding provider (one API key), OR at one local Ollama
   (`ollama pull <chat-model>` + an embedding model). Same models = fair test.
   Local models eat the same RAM the stacks need — on 16 GB, cloud models make
   the POC dramatically easier. Decide once, use for both.

## B. UTM Ubuntu VM for RAGFlow (one-time, ~30 min)

UTM is free and uses Apple's Virtualization framework (fast on M-series).

1. Install UTM: `brew install --cask utm` (or utmapp.com).
2. Download **Ubuntu Server 24.04 ARM64** ISO from ubuntu.com/download/server/arm
   (use the ARM64 image — an x86 image will be emulated and painfully slow).
3. UTM → Create New → **Virtualize** (not Emulate) → Linux →
   - RAM: **8192 MB minimum, 12288–16384 MB if your Mac has 24 GB+**
     (RAGFlow's documented floor is 16 GB total system RAM; give the VM as
     much as you can while leaving macOS ≥ 8 GB)
   - CPU cores: **4**
   - Storage: **64 GB** (RAGFlow asks for ≥ 50 GB disk)
   - Shared Directory: share this repo's folder — you'll see it in the VM
     (or just `git clone` this repo inside the VM; simpler and avoids
     shared-folder permission quirks).
4. Install Ubuntu (defaults; check “Install OpenSSH server” if you want to
   SSH in from the Mac terminal — recommended).
5. Inside the VM, install Docker:

```bash
sudo apt update && sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
 | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER   # log out/in once after this
docker version && docker compose version
```

6. Note the VM's IP (`ip a`, look for `192.168.64.x` under UTM Shared Network).
   From the Mac you can then open `http://<vm-ip>` for the RAGFlow UI and point
   bench.py at it. Or do everything in the VM's own browser/terminal.

> Alternative VM tools if you already have them: Parallels / VMware Fusion
> (same Ubuntu ARM64 image, same sizing), or Lima/Colima for a CLI-only Linux
> VM. UTM is documented here because it is free and needs no account.

## C. Sanity checks before you blame a RAG system

```bash
# Mac, OpenRAG side
docker ps                       # all openrag-* containers up?
curl -s http://localhost:3000   # UI responds?
curl -s http://localhost:5001   # Docling serve responds (host process)?

# Inside the VM, RAGFlow side
sudo sysctl vm.max_map_count    # must be >= 262144 (start.sh sets it)
docker ps                       # ragflow + es/mysql/minio/redis healthy?
curl -f http://localhost/api/v1/system/healthz   # RAGFlow 1.0 health endpoint
```

Full troubleshooting lists live in each POC's README.
