# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Black Oracle is a RAG (Retrieval Augmented Generation) system that queries a personal Obsidian PKM vault using a local LLM. It has two stages:

1. **Ingestion** (offline): Dagster pipeline loads markdown files, chunks them, embeds with HuggingFace, and stores in ChromaDB.
2. **Inference** (online): FastAPI server retrieves relevant chunks from ChromaDB and generates answers via Ollama.

## Development Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run ingestion pipeline (then open localhost:3000, materialize all assets)
dagster dev -f ingestion_pipeline.py

# Run inference API server (localhost:8000)
python main.py

# Test vector DB retrieval directly
python test_retrieval.py

# Test inference API
bash test_inference.sh
# or manually:
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"question": "Your question here"}'
```

## External Dependencies

- **Ollama**: Must be running at `http://localhost:11434` with `llama3` model pulled (`ollama pull llama3`)
- **Data**: `./data/` is a symlink to `/home/maciek/obsidian-pkm` (Obsidian vault with `.md` files)
- **ChromaDB**: Persisted locally at `./chroma_db/` (collection name: `local_docs`)

## Architecture

### ingestion_pipeline.py
Dagster asset graph with three assets:
- `raw_documents`: Loads all `.md` files from `./data` via `DirectoryLoader`
- `processed_chunks`: Splits into 1000-char chunks with 100-char overlap using `RecursiveCharacterTextSplitter`
- `vector_store`: Embeds with `HuggingFaceEmbeddings(all-MiniLM-L6-v2)` and stores in ChromaDB

### main.py
FastAPI app with single endpoint `POST /ask`:
- Loads same ChromaDB collection and embeddings model as ingestion
- Retrieves top 10 relevant chunks (k=10)
- Uses LangChain `load_qa_chain` with Ollama (`llama3`) to generate answers
- Uses `langchain_classic.chains` due to LangChain v1.0 API breaking changes

## LangChain Version Note

This project uses `langchain_classic.chains` (not `langchain.chains`) because of breaking API changes in LangChain v1.0. Keep this in mind when adding new LangChain functionality.
