import os
from dagster import asset, Config
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# Configuration for reproducibility
class IngestionConfig(Config):
    source_dir: str = "./data"
    persist_dir: str = "./chroma_db"
    collection_name: str = "local_docs"

@asset
def raw_documents(config: IngestionConfig):
    """Load documents from a local directory."""
    loader = DirectoryLoader(config.source_dir, glob="**/*.md", loader_cls=TextLoader)
    docs = loader.load()
    print(f"Loaded {len(docs)} documents.")
    return docs

@asset
def processed_chunks(raw_documents):
    """Split documents into semantic chunks to fit LLM context windows."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=100,
        add_start_index=True
    )
    chunks = text_splitter.split_documents(raw_documents)
    return chunks

@asset
def vector_store(config: IngestionConfig, processed_chunks):
    """Embed chunks and upsert into the Vector Database."""
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    vector_db = Chroma.from_documents(
        documents=processed_chunks,
        embedding=embeddings,
        persist_directory=config.persist_dir,
        collection_name=config.collection_name
    )
    return f"Indexed {len(processed_chunks)} chunks into {config.collection_name}."
