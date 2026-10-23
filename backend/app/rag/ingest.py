"""Loads docs -> splits into chunks -> embeds -> stores in the vector store.
Laptop with VECTOR_STORE=chroma:  python -m app.rag.ingest   (re-running wipes the old data first)
Cloud (memory store): the server calls ensure_knowledge_base() at start, nothing to run by hand."""
import threading
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.vectorstore import get_vectorstore, is_empty, reset_vectorstore

DOCS_DIR = Path(__file__).parent / "docs"

KB_STARTED = threading.Event()  # set when the server begins preparing the knowledge base
KB_READY = threading.Event()    # set when it is finished (also when it failed)


def load_documents() -> list[Document]:
    docs = []
    for path in sorted(DOCS_DIR.glob("*.txt")):
        docs.append(Document(page_content=path.read_text(encoding="utf-8"),
                             metadata={"source": path.name}))
    return docs


def split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    return splitter.split_documents(docs)


def ingest(embeddings=None) -> int:
    docs = load_documents()
    chunks = split_documents(docs)

    store = reset_vectorstore(embeddings)  # wipe old data
    store.add_documents(chunks)
    print(f"Ingested {len(docs)} documents as {len(chunks)} chunks into the knowledge base.")
    return len(chunks)


def ensure_knowledge_base() -> None:
    """Builds the knowledge base when the store is empty (cloud hosts start with an empty disk).
    Never raises: if it fails, the chat still works and the Knowledge Agent says it is not sure."""
    KB_STARTED.set()
    try:
        if is_empty(get_vectorstore()):
            ingest()
    except Exception as e:
        print(f"[knowledge base] could not be prepared: {e}")
    finally:
        KB_READY.set()


if __name__ == "__main__":
    ingest()
