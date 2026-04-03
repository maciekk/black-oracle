#!/bin/bash
# cold-start.sh — bring up (or shut down) the Black Oracle serving stack
# Usage: ./cold-start.sh [--dagster] [--debug]
#        ./cold-start.sh --shutdown [--ollama]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_URL="http://localhost:11434"
API_URL="http://localhost:8000"
DAGSTER_URL="http://localhost:3000"
WITH_DAGSTER=false
DEBUG=false
SHUTDOWN=false
SHUTDOWN_OLLAMA=false

for arg in "$@"; do
    [[ "$arg" == "--dagster" ]]  && WITH_DAGSTER=true
    [[ "$arg" == "--debug" ]]    && DEBUG=true
    [[ "$arg" == "--shutdown" ]] && SHUTDOWN=true
    [[ "$arg" == "--ollama" ]]   && SHUTDOWN_OLLAMA=true
done

# ── Shutdown ──────────────────────────────────────────────────────────────────
if $SHUTDOWN; then
    bold() { printf "\033[1m%s\033[0m\n" "$*"; }
    ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
    info() { printf "  %s\n" "$*"; }
    bold "Shutting down Black Oracle"
    pkill -f "oracle.py"      2>/dev/null && ok "stopped oracle.py"      || info "oracle.py was not running"
    pkill -f "dagster dev"    2>/dev/null && ok "stopped dagster"         || info "dagster was not running"
    if $SHUTDOWN_OLLAMA; then
        pkill -f "ollama serve" 2>/dev/null && ok "stopped ollama"        || info "ollama was not running"
    else
        info "ollama left running (pass --ollama to stop it too)"
    fi
    exit 0
fi

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
    local url="$1" label="$2" retries="${3:-30}"
    for i in $(seq 1 $retries); do
        if curl -sf "$url" >/dev/null 2>&1; then
            ok "$label is up"
            return 0
        fi
        sleep 1
    done
    fail "$label did not become ready after ${retries}s"
}

# Wait for a pattern to appear in a log file, then confirm via HTTP.
# Falls back to a long HTTP-only poll when no log file is available (--debug).
wait_for_api() {
    local url="$1" log="$2" pattern="$3" label="$4"
    if $DEBUG; then
        wait_for "$url" "$label" 180
        return
    fi
    local retries=180
    info "waiting for model to load..."
    for i in $(seq 1 $retries); do
        if grep -q "$pattern" "$log" 2>/dev/null; then
            break
        fi
        if [[ $i -eq $retries ]]; then
            fail "$label: model did not finish loading after ${retries}s (check $log)"
        fi
        sleep 1
    done
    wait_for "$url" "$label"
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

info "checking for gemma4:e4b model..."
if ollama list 2>/dev/null | grep -q "^gemma4:e4b"; then
    ok "gemma4:e4b available"
else
    info "pulling gemma4:e4b (this may take a while)..."
    ollama pull gemma4:e4b || fail "failed to pull gemma4:e4b"
    ok "gemma4:e4b pulled"
fi

# ── FastAPI / oracle.py ───────────────────────────────────────────────────────
bold "FastAPI (oracle.py)"
if curl -sf "$API_URL/docs" >/dev/null 2>&1; then
    ok "already running"
else
    info "starting..."
    eval "TOKENIZERS_PARALLELISM=false uv run python oracle.py $redir_api &"
    wait_for_api "$API_URL/docs" /tmp/black-oracle-api.log "BertModel LOAD REPORT" "FastAPI"
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
info "Run: ./chat.py"
