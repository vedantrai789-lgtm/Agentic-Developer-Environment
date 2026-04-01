#!/usr/bin/env bash
# ADE bootstrap — one command to set up and start everything.
# Usage: bash scripts/bootstrap.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[ADE]${NC} $*"; }
warn()  { echo -e "${YELLOW}[ADE]${NC} $*"; }
fail()  { echo -e "${RED}[ADE]${NC} $*"; exit 1; }

# ── 1. Check prerequisites ──────────────────────────────────────────────
info "Checking prerequisites..."

command -v docker  >/dev/null 2>&1 || fail "Docker is not installed."
docker info        >/dev/null 2>&1 || fail "Docker daemon is not running. Start Docker Desktop."
command -v node    >/dev/null 2>&1 || warn "Node.js not found — UI will be skipped."

# Locate uv
UV=""
if command -v uv >/dev/null 2>&1; then
    UV="uv"
elif [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
else
    fail "uv is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
info "Using uv at: $UV"

# ── 2. .env file ────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    warn ".env created from template. Edit it to add your API keys, then re-run."
    warn "At minimum set: ANTHROPIC_API_KEY"
    exit 1
fi

# Check ANTHROPIC_API_KEY is set
if grep -q "^ANTHROPIC_API_KEY=sk-ant-xxxxx" .env || grep -q "^ANTHROPIC_API_KEY=$" .env; then
    fail "ANTHROPIC_API_KEY is not set in .env. Add your key and re-run."
fi

# ── 3. Python venv + dependencies ───────────────────────────────────────
if [ ! -d .venv ]; then
    info "Creating Python virtual environment..."
    $UV venv .venv
fi

info "Installing Python dependencies..."
$UV pip install -e ".[dev]" --quiet 2>&1 | tail -1 || $UV pip install -e ".[dev]"

# ── 4. Docker services ──────────────────────────────────────────────────
info "Starting PostgreSQL and Redis..."
docker compose up -d

info "Waiting for services to be healthy..."
RETRIES=30
until docker compose ps --format json 2>/dev/null | grep -q '"healthy"' || [ $RETRIES -eq 0 ]; do
    sleep 1
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    warn "Services may not be fully healthy yet, but continuing..."
fi

# ── 5. Database migrations ──────────────────────────────────────────────
info "Running database migrations..."
.venv/bin/alembic upgrade head

# ── 6. Optional: build sandbox image ────────────────────────────────────
if [ -f ade/sandbox/Dockerfile.sandbox ]; then
    if ! docker image inspect ade-sandbox:latest >/dev/null 2>&1; then
        info "Building sandbox Docker image (first time only)..."
        docker build -t ade-sandbox:latest -f ade/sandbox/Dockerfile.sandbox . || \
            warn "Sandbox image build failed. Set SANDBOX_BACKEND=subprocess in .env as fallback."
    fi
fi

# ── 7. Optional: install UI dependencies ────────────────────────────────
if command -v node >/dev/null 2>&1 && [ -f ade/ui/package.json ]; then
    if [ ! -d ade/ui/node_modules ]; then
        info "Installing UI dependencies..."
        (cd ade/ui && npm install --silent)
    fi
fi

# ── 8. Start the server ─────────────────────────────────────────────────
echo ""
info "============================================"
info "  ADE is ready!"
info "============================================"
info ""
info "  API server:  http://localhost:8000"
info "  Health check: http://localhost:8000/health"
info ""
info "  Quick start:"
info "    ade init /path/to/project --name my-project"
info "    ade task my-project \"Add unit tests\""
info ""
if command -v node >/dev/null 2>&1 && [ -d ade/ui/node_modules ]; then
    info "  UI (separate terminal):"
    info "    cd ade/ui && npm run dev"
    info ""
fi
info "  Starting API server now..."
info ""

.venv/bin/ade serve
