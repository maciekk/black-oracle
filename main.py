from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain_classic.chains import RetrievalQA, ConversationalRetrievalChain
from langchain_core.prompts import PromptTemplate
import config

app = FastAPI(title="Production RAG API")

embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
vector_db = Chroma(
    persist_directory=config.CHROMA_PERSIST_DIR,
    embedding_function=embeddings,
    collection_name=config.CHROMA_COLLECTION_NAME,
)

llm = OllamaLLM(
    model=config.OLLAMA_MODEL,
    base_url=config.OLLAMA_BASE_URL,
)

_QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=(
        "You are a Personal Knowledge Assistant. The context "
        "provided below consists of my personal thoughts, notes, "
        "and documentation from my private Obsidian vault.\n\n"
        "When answering:\n"
        "1. Refer to me as \"you\" and to the notes as "
        "\"your notes\" or \"your thoughts.\"\n"
        "2. Never refer to the author as \"the individual\" "
        "or \"the user.\"\n"
        "3. If the notes say \"I should do X,\" your answer "
        "should be \"You noted that you should do X.\"\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}\n"
        "Answer:"
    ),
)

_retriever = vector_db.as_retriever(search_kwargs={"k": config.RETRIEVER_K})

ask_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=_retriever,
    return_source_documents=True,
)

chat_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=_retriever,
    chain_type="stuff",
    return_source_documents=True,
    combine_docs_chain_kwargs={"prompt": _QA_PROMPT},
)

class QueryRequest(BaseModel):
    question: str

class ChatRequest(BaseModel):
    question: str
    chat_history: list[list[str]] = []  # list of [human, ai] pairs

@app.post("/ask")
async def ask_question(request: QueryRequest):
    """
    Standard RAG Endpoint: 
    1. Retrieve relevant chunks from ChromaDB.
    2. Augment the prompt with context.
    3. Generate response via Ollama.
    """
    try:
        response = ask_chain.invoke(request.question)
        answer = response["result"]

        # 'source_documents' is a list of Document objects
        sources = [
            {
                "content": doc.page_content[:200], # Preview of what was read
                "metadata": doc.metadata           # File path, tags, etc.
            }
            for doc in response["source_documents"]
        ]

        return {
            "answer": answer,
            "sources": sources
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Conversational RAG Endpoint:
    Retrieves relevant chunks and generates a response aware of prior conversation turns.
    """
    try:
        # Pydantic parses JSON arrays as lists; LangChain's internals expect tuples
        history = [(h, a) for h, a in request.chat_history]
        response = chat_chain.invoke({"question": request.question, "chat_history": history})
        answer = response["answer"]
        sources = [
            {
                "content": doc.page_content[:200],
                "metadata": doc.metadata,
            }
            for doc in response["source_documents"]
        ]
        return {"answer": answer, "sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
