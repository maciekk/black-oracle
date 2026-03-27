---
name: Project overview
description: Black Oracle RAG system — architecture, key files, and settled decisions
type: project
---

Black Oracle is a local RAG system querying an Obsidian vault via Dagster ingestion + FastAPI inference + Ollama (llama3). The main chat client is `chat.py` (Textual TUI).

**Why:** Personal knowledge assistant; all data stays on-device.

**Settled decisions:**
- Chunk size stays at 1000 chars / 100 overlap — user explicitly decided not to increase it
- k=10 retrieved chunks per query
- `langchain_classic.chains` used (not `langchain.chains`) due to LangChain v1.0 breaking changes
- `chat.py` is the primary interface; `test_chat.sh` and `test_inference.sh` are legacy helpers
