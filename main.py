from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain_classic.chains import RetrievalQA

app = FastAPI(title="Production RAG API")

# Setup: This should ideally be a singleton or dependency in FastAPI
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(
    persist_directory="./chroma_db", 
    embedding_function=embeddings,
    collection_name="local_docs"
)

# Use a local model (e.g., llama3 or mistral)
# MacOS form
#llm = Ollama(model="llama3")
# Linux form
llm = Ollama(
    model="llama3", 
    base_url="http://localhost:11434" # Ensure no trailing slash
)

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_question(request: QueryRequest):
    """
    Standard RAG Endpoint: 
    1. Retrieve relevant chunks from ChromaDB.
    2. Augment the prompt with context.
    3. Generate response via Ollama.
    """
    try:
        # Create a chain that handles the retrieval and prompt augmentation
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff", # 'Stuff' simply pushes all retrieved docs into the prompt
            retriever=vector_db.as_retriever(search_kwargs={"k": 10})
        )

        response = qa_chain.invoke(request.question)
        return {"answer": response["result"]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
