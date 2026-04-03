OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma4:e4b"

CHROMA_PERSIST_DIR = "./chroma_db"
CHROMA_COLLECTION_NAME = "local_docs"
CHROMA_SOURCE_DIR = "./data"

EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"

# "mmr" reduces redundant chunks via Maximum Marginal Relevance.
# "similarity_score_threshold" filters out low-relevance chunks instead.
# These are mutually exclusive — pick one.
RETRIEVER_SEARCH_TYPE = "mmr"
RETRIEVER_K = 10
RETRIEVER_FETCH_K = 30        # mmr only: candidate pool before diversity re-ranking
RETRIEVER_SCORE_THRESHOLD = 0.4  # similarity_score_threshold only: minimum relevance score
