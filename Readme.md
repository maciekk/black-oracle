# Black Oracle

A local RAG (Retrieval-Augmented Generation) system for querying a personal
Obsidian PKM vault using a local LLM. All data stays on-device.

> Project ideation: [Google Gemini Pro session](https://gemini.google.com/app/89e20025d1622a80)

![Black Oracle TUI](screenshot-chat.png)

---

## How it works

1. **Ingestion** (run once, or when notes change): A Dagster pipeline loads
   all `.md` files from the vault, splits them into chunks, embeds them with
   HuggingFace, and stores the vectors in ChromaDB.

2. **Inference** (run anytime): A FastAPI server retrieves relevant chunks
   from ChromaDB and generates answers via a local Ollama model.

---

## Prerequisites

- [Ollama](https://ollama.com) installed and running
- Python 3.11+
- `./data` symlinked to your Obsidian vault (directory of `.md` files)

Pull the LLM model before first use:

```bash
ollama pull llama3
```

### Alternative: Docker-based infrastructure

Instead of running Ollama and ChromaDB natively, you can bring them up with
Docker:

```bash
docker run -d -p 8000:8000 chromadb/chroma
docker run -d -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install langchain-chroma langchain-huggingface langchain-community \
            langchain-classic dagster dagster-webserver \
            fastapi uvicorn sentence-transformers rich textual
```

---

## Usage

### 1. Ingest your vault

```bash
dagster dev -f ingestion_pipeline.py
```

Open [localhost:3000](http://localhost:3000), go to **Lineage**, and click
**Materialize All**. This populates ChromaDB at `./chroma_db/`. Re-run
whenever your notes change significantly.

### 2. Start the inference server

```bash
source .venv/bin/activate
python main.py
```

Server runs at [localhost:8000](http://localhost:8000).

### 3. Query

**Single-shot (non-conversational):**

```bash
bash test_inference.sh
# or manually:
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"question": "Your question here"}'
```

**Conversational chat (maintains history across turns):**

```bash
python chat.py
```

Press `Ctrl+S` to toggle source previews in the right-hand panel. Ctrl+C to exit.

---

## Architecture

| File | Role |
|---|---|
| `ingestion_pipeline.py` | Dagster pipeline: load → chunk → embed → store in ChromaDB |
| `main.py` | FastAPI server: `/ask` (stateless) and `/chat` (conversational) endpoints |
| `test_inference.sh` | Single-shot CLI query tool |
| `chat.py` | Interactive multi-turn chat UI (uses `rich` for formatting) |
| `test_retrieval.py` | Direct ChromaDB retrieval test (no LLM) |

### Endpoints

- `POST /ask` — stateless RAG query; returns `answer` + `sources`
- `POST /chat` — conversational RAG; accepts `question` and
  `chat_history` (`[[human, ai], ...]`); returns `answer` + `sources`

### LangChain version note

This project uses `langchain_classic.chains` (not `langchain.chains`) due to
breaking API changes in LangChain v1.0. Keep this in mind when adding new
LangChain functionality.

---

## Future Potential Work

- **Server-side conversation state**: The `/chat` endpoint requires the client to send the full `chat_history` on every turn. A session-keyed store with a max-history limit would offload that burden and prevent unbounded prompt growth.

- **Incremental ingestion**: The Dagster pipeline rebuilds the entire ChromaDB collection on every run. An upsert strategy — hashing chunks by `(source, start_index)` and only embedding new/changed ones — would make re-ingestion practical for large or frequently-updated vaults.

- **Token budget guard for `k=10`**: Stuffing 10 chunks into the prompt can overflow the LLM's context window on long documents. Either add a dynamic token budget check or switch to a `map_reduce` or `refine` chain type for larger result sets.

- **Migrate off `langchain_classic`**: `langchain_classic` is a compatibility shim for pre-v1.0 LangChain APIs. Migrating to LCEL (LangChain Expression Language) pipelines would restore active maintenance, improve composability, and unlock async streaming out of the box.

- **Structured error handling**: Both endpoints catch all exceptions and return HTTP 500 with `str(e)`. ChromaDB connection failures, Ollama timeouts, and malformed inputs should produce distinct status codes and be logged separately.
