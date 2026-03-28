#!/bin/bash
# cold-start.sh — bring up Black Oracle serving stack
# Usage: ./cold-start.sh [--dagster] [--debug]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_URL="http://localhost:11434"
API_URL="http://localhost:8000"
DAGSTER_URL="http://localhost:3000"
WITH_DAGSTER=false
DEBUG=false

for arg in "$@"; do
    [[ "$arg" == "--dagster" ]] && WITH_DAGSTER=true
    [[ "$arg" == "--debug" ]] && DEBUG=true
done

# In debug mode services log to the terminal; otherwise to /tmp files.
redir_api=""
redir_dagster=""
redir_ollama=""
if ! $DEBUG; then
    redir_api=">/tmp/black-oracle-api.log 2>&1"
    redir_dagster=">/tmp/black-oracle-dagster.log 2>&1"
    redir_ollama=">/tmp/ollama.log 2>&1"
fi

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
    eval "ollama serve $redir_ollama &"
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

# ── FastAPI / oracle.py ───────────────────────────────────────────────────────
bold "FastAPI (oracle.py)"
if curl -sf "$API_URL/docs" >/dev/null 2>&1; then
    ok "already running"
else
    info "starting..."
    eval "TOKENIZERS_PARALLELISM=false uv run python oracle.py $redir_api &"
    wait_for "$API_URL/docs" "FastAPI"
fi

# ── Dagster (optional) ────────────────────────────────────────────────────────
if $WITH_DAGSTER; then
    bold "Dagster"
    if curl -sf "$DAGSTER_URL" >/dev/null 2>&1; then
        ok "already running"
    else
        info "starting..."
        eval "uv run dagster dev -f ingestion_pipeline.py $redir_dagster &"
        wait_for "$DAGSTER_URL" "Dagster"
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo
bold "Stack ready"
info "API:     $API_URL"
$WITH_DAGSTER && info "Dagster: $DAGSTER_URL"
if $DEBUG; then
    info "Logs:    (debug mode — output above)"
else
    info "Logs:    /tmp/black-oracle-api.log"
    $WITH_DAGSTER && info "         /tmp/black-oracle-dagster.log"
fi
info ""
info "Run: bash test_chat.sh"
