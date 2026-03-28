#!/bin/bash
# cold-start.sh — bring up Black Oracle serving stack
# Usage: ./cold-start.sh [--dagster]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_URL="http://localhost:11434"
API_URL="http://localhost:8000"
DAGSTER_URL="http://localhost:3000"
WITH_DAGSTER=false

for arg in "$@"; do
    [[ "$arg" == "--dagster" ]] && WITH_DAGSTER=true
done

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
info() { printf "  %s\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*"; exit 1; }

wait_for() {
    local url="$1" label="$2" retries=30
    for i in $(seq 1 $retries); do
        if curl -sf "$url" >/dev/null 2>&1; then
            ok "$label is up"
            return 0
        fi
        sleep 1
    done
    fail "$label did not become ready after ${retries}s"
}

cd "$SCRIPT_DIR"

# ── Ollama ────────────────────────────────────────────────────────────────────
bold "Ollama"
if curl -sf "$OLLAMA_URL" >/dev/null 2>&1; then
    ok "already running"
else
    info "starting..."
    ollama serve >/tmp/ollama.log 2>&1 &
    wait_for "$OLLAMA_URL" "ollama"
fi

info "checking for llama3 model..."
if ollama list 2>/dev/null | grep -q "^llama3"; then
    ok "llama3 available"
else
    info "pulling llama3 (this may take a while)..."
    ollama pull llama3 || fail "failed to pull llama3"
    ok "llama3 pulled"
fi

# ── FastAPI / main.py ─────────────────────────────────────────────────────────
bold "FastAPI (main.py)"
if curl -sf "$API_URL/docs" >/dev/null 2>&1; then
    ok "already running"
else
    info "starting..."
    source "$SCRIPT_DIR/.venv/bin/activate"
    TOKENIZERS_PARALLELISM=false python main.py >/tmp/black-oracle-api.log 2>&1 &
    wait_for "$API_URL/docs" "FastAPI"
fi

# ── Dagster (optional) ────────────────────────────────────────────────────────
if $WITH_DAGSTER; then
    bold "Dagster"
    if curl -sf "$DAGSTER_URL" >/dev/null 2>&1; then
        ok "already running"
    else
        info "starting..."
        source "$SCRIPT_DIR/.venv/bin/activate"
        dagster dev -f ingestion_pipeline.py >/tmp/black-oracle-dagster.log 2>&1 &
        wait_for "$DAGSTER_URL" "Dagster"
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo
bold "Stack ready"
info "API:     $API_URL"
$WITH_DAGSTER && info "Dagster: $DAGSTER_URL"
info "Logs:    /tmp/black-oracle-api.log"
$WITH_DAGSTER && info "         /tmp/black-oracle-dagster.log"
info ""
info "Run: bash test_chat.sh"
