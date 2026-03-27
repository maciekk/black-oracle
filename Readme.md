# Black Oracle

A local RAG (Retrieval-Augmented Generation) system for querying a personal
Obsidian PKM vault using a local LLM. All data stays on-device.

> Project ideation: [Google Gemini Pro session](https://gemini.google.com/app/89e20025d1622a80)

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
            fastapi uvicorn sentence-transformers
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
bash test_chat.sh
```

Type `quit` or press Ctrl+C to exit. After each answer, you will be prompted
to optionally show the source documents that informed the response.

---

## Architecture

| File | Role |
|---|---|
| `ingestion_pipeline.py` | Dagster pipeline: load → chunk → embed → store in ChromaDB |
| `main.py` | FastAPI server: `/ask` (stateless) and `/chat` (conversational) endpoints |
| `test_inference.sh` | Single-shot CLI query tool |
| `test_chat.sh` | Interactive multi-turn chat loop |
| `test_retrieval.py` | Direct ChromaDB retrieval test (no LLM) |

### Endpoints

- `POST /ask` — stateless RAG query; returns `answer` + `sources`
- `POST /chat` — conversational RAG; accepts `question` and
  `chat_history` (`[[human, ai], ...]`); returns `answer` + `sources`

### LangChain version note

This project uses `langchain_classic.chains` (not `langchain.chains`) due to
breaking API changes in LangChain v1.0. Keep this in mind when adding new
LangChain functionality.
