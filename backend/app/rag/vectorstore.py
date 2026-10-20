"""Embeddings + ChromaDB setup. No API key needed (local embeddings, local Chroma)."""
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings

COLLECTION_NAME = "support_kb"


def get_embeddings():
    # Runs locally. First run downloads the model (~90 MB), then it is cached.
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)


def get_vectorstore(embeddings=None) -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings or get_embeddings(),
        persist_directory=settings.CHROMA_DIR,
    )


def get_retriever(k: int = 3):
    """Used by the search_knowledge_base tool (Step 4)."""
    return get_vectorstore().as_retriever(search_kwargs={"k": k})
