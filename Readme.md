## Random Notes

Project ideation done in Google Gemini Pro.
Src: https://gemini.google.com/app/89e20025d1622a80

Potential quick way to bring up all the infra:

```
# Start a vector database and an LLM server
docker run -d -p 8000:8000 chromadb/chroma
docker run -d -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
```

### Ingestion piece:

```
$ pip install dagster dagster-webserver langchain langchain-chroma langchain-huggingface langchain-community unstructured
$ dagster dev -f ingestion_pipeline.py
bring up browser on localhost:3000
-> Lineage -> Materialize all
hit error on last box, `vector_store`
ah, need: pip install sentence-transformers
```


Success

### Inference
In order to run `main.py`, needed:
  `pip install fastapi`

Ugh, also:
	`pip install langchain-classic`
and then modify `main.py` to use:
	`from langchain_classic.chains import ...`

This has to do with some sort of LangChain API changes as of 1.0...

Ah, crud, and one of the recent changes made us hit "this Python is externally managed", so need to use venv:
```
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install langchain-chroma langchain-huggingface langchain-community dagster dagster-webserver fastapi uvicorn sentence-transformers
```


Hitting 404 on the inferenec server.

$ ollama list

Ah, no models.

-> $ ollama pull llama3

gt
