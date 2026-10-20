"""Knowledge Agent tool: semantic search over the company knowledge base (ChromaDB). No API key."""
from functools import lru_cache

from langchain_core.tools import tool

from app.rag.vectorstore import get_retriever


@lru_cache(maxsize=1)
def _retriever():
    # Cached so the embedding model loads only once, not on every question.
    return get_retriever(k=3)


@tool
def search_knowledge_base(query: str) -> str:
    """Search company policies and FAQs (refunds, shipping, warranty, account, support hours).
    Use this for any general question about how the company works."""
    docs = _retriever().invoke(query)
    if not docs:
        return "No relevant information found in the knowledge base."
    return "\n\n".join(f"[{d.metadata.get('source', 'unknown')}] {d.page_content}" for d in docs)
