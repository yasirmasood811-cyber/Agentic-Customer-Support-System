"""Embeddings + vector store for the knowledge base.
Cloud default: Gemini embeddings (GOOGLE_API_KEY) + an in-memory store that is rebuilt at server start.
Laptop option: EMBEDDINGS_PROVIDER=local (MiniLM, no key) and VECTOR_STORE=chroma (kept on disk)."""
from langchain_core.vectorstores import InMemoryVectorStore

from app.config import settings

COLLECTION_NAME = "support_kb"
_memory_store = None


def get_embeddings():
    if settings.EMBEDDINGS_PROVIDER == "local":
        from langchain_huggingface import HuggingFaceEmbeddings  # only installed on a laptop
        return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(model=settings.GEMINI_EMBEDDING_MODEL, google_api_key=settings.GOOGLE_API_KEY)


def _use_chroma() -> bool:
    return settings.VECTOR_STORE == "chroma"


def get_vectorstore(embeddings=None):
    global _memory_store
    if not _use_chroma():
        if _memory_store is None:
            _memory_store = InMemoryVectorStore(embeddings or get_embeddings())
        return _memory_store
    from langchain_chroma import Chroma
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings or get_embeddings(),
        persist_directory=settings.CHROMA_DIR,
    )


def reset_vectorstore(embeddings=None):
    """Returns the store with all old documents removed, ready for a fresh ingest."""
    store = get_vectorstore(embeddings)
    if _use_chroma():
        store.reset_collection()
    else:
        store.store.clear()  # in place, so retrievers created earlier keep working
    return store


def is_empty(store) -> bool:
    if isinstance(store, InMemoryVectorStore):
        return len(store.store) == 0
    return store._collection.count() == 0


def get_retriever(k: int = 3):
    """Used by the search_knowledge_base tool."""
    return get_vectorstore().as_retriever(search_kwargs={"k": k})
