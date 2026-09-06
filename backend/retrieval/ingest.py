"""
ingest.py
The Phase 2 entry point. Run this once (and again whenever data/raw/ changes)
to build the ChromaDB index that retrieval_agent.py queries at runtime.

Usage:
    python retrieval/ingest.py
"""

import os
import time
import chromadb
import ollama

from loader import load_all_documents
from chunker import chunk_text

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_store")
COLLECTION_NAME = "financial_docs"
EMBED_MODEL = "nomic-embed-text"


def embed(text: str, is_query: bool = False) -> list[float]:
    """
    nomic-embed-text requires a task prefix on every input to produce good
    embeddings — "search_document: " for indexed content, "search_query: "
    for queries at retrieval time. Omitting this measurably hurts retrieval
    quality even though the model still returns a vector without it.
    """
    prefix = "search_query: " if is_query else "search_document: "
    response = ollama.embeddings(model=EMBED_MODEL, prompt=prefix + text)
    return response["embedding"]


def build_index():
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Fresh start each run — simplest correct behavior for a portfolio project.
    # (For an incremental/production version, you'd diff against existing IDs instead.)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print("Loading documents...")
    documents = load_all_documents()
    print(f"Loaded {len(documents)} documents.\n")

    total_chunks = 0
    start_time = time.time()

    for filename, raw_text in documents.items():
        chunks = chunk_text(raw_text)
        if not chunks:
            print(f"  ! {filename}: no text extracted, skipping")
            continue

        print(f"Indexing {filename}: {len(chunks)} chunks...")

        # Embed in small batches to keep memory/requests reasonable on large 10-Ks
        batch_size = 20
        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start: batch_start + batch_size]
            embeddings = [embed(chunk) for chunk in batch]
            ids = [f"{filename}_{batch_start + i}" for i in range(len(batch))]
            metadatas = [{"source": filename, "chunk_index": batch_start + i} for i in range(len(batch))]

            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=batch,
                metadatas=metadatas,
            )

        total_chunks += len(chunks)

    elapsed = time.time() - start_time
    print(f"\nDone. Indexed {total_chunks} chunks across {len(documents)} documents in {elapsed:.1f}s.")
    print(f"ChromaDB persisted at: {CHROMA_PATH}")


if __name__ == "__main__":
    build_index()