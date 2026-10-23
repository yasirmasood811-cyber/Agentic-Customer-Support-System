"""Knowledge Agent tool: semantic search over the company knowledge base.
Key used (cloud default): GOOGLE_API_KEY for the embeddings of the question."""
from functools import lru_cache

from langchain_core.tools import tool

from app.rag.ingest import KB_READY, KB_STARTED
from app.rag.vectorstore import get_retriever

KB_WAIT_SECONDS = 30  # how long to wait if the server is still building the knowledge base (cold start)


@lru_cache(maxsize=1)
def _retriever():
    # Cached so the store/embedding client is created only once, not on every question.
    return get_retriever(k=3)


@tool
def search_knowledge_base(query: str) -> str:
    """Search company policies and FAQs (refunds, shipping, warranty, account, support hours).
    Use this for any general question about how the company works."""
    if KB_STARTED.is_set() and not KB_READY.is_set():
        KB_READY.wait(timeout=KB_WAIT_SECONDS)
    try:
        docs = _retriever().invoke(query)
    except Exception as e:
        return ("The knowledge base is temporarily unavailable "
                f"({str(e)[:100]}). Say you are not sure and offer a human agent.")
    if not docs:
        return "No relevant information found in the knowledge base."
    return "\n\n".join(f"[{d.metadata.get('source', 'unknown')}] {d.page_content}" for d in docs)
