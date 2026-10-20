"""Loads docs -> splits into chunks -> embeds -> stores in ChromaDB.
Run from backend/:  python -m app.rag.ingest
Re-running wipes the old collection first, so there are no duplicates."""
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.vectorstore import get_embeddings, get_vectorstore

DOCS_DIR = Path(__file__).parent / "docs"


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

    store = get_vectorstore(embeddings)
    store.reset_collection()  # wipe old data
    store.add_documents(chunks)
    print(f"Ingested {len(docs)} documents as {len(chunks)} chunks into ChromaDB.")
    return len(chunks)


if __name__ == "__main__":
    ingest()
