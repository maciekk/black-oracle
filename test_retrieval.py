from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# 1. Initialize the exact same embedding model used in your Dagster pipeline
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 2. Point to your generated database
vector_db = Chroma(
    persist_directory="./chroma_db", 
    embedding_function=embeddings,
    collection_name="local_docs"
)

def run_test(query):
    print(f"\n--- Testing Query: '{query}' ---")

    # We ask for the top 2 matches
    results = vector_db.similarity_search_with_score(query, k=2)

    for doc, score in results:
        # Score: Lower is usually "closer" (better) for L2 distance
        print(f"\n[Score: {score:.4f}] Content Preview:")
        print(f"{doc.page_content[:200]}...") 
        print(f"Source: {doc.metadata.get('source', 'Unknown')}")

if __name__ == "__main__":
    # Test with a specific phrase you know exists in your Obsidian Vault
    run_test("What are my notes on kettlebell swings?")
