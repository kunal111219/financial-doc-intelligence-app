"""
diagnose_penalty_query.py
One-off diagnostic: finds exactly where the two contract chunks rank
against the "penalty clause" query, out of all 2934 chunks — instead of
only looking at the top 3, which hides whether they're close-but-not-first
or genuinely nowhere near a match.
"""

import os
import chromadb
import ollama

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_store")
COLLECTION_NAME = "financial_docs"
EMBED_MODEL = "nomic-embed-text"


def embed(text: str, is_query: bool = False) -> list[float]:
    prefix = "search_query: " if is_query else "search_document: "
    return ollama.embeddings(model=EMBED_MODEL, prompt=prefix + text)["embedding"]


def main():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)

    query = "penalty clause for late payment"
    query_emb = embed(query, is_query=True)

    # Ask for ALL results (n_results = total chunk count) so we can find
    # the actual rank of the contract chunks, not just the top 3.
    total = collection.count()
    results = collection.query(query_embeddings=[query_emb], n_results=total)

    ids = results["ids"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    print(f"Query: {query!r}\n")
    for rank, (doc_id, meta, dist) in enumerate(zip(ids, metadatas, distances), start=1):
        if "contract" in meta["source"]:
            print(f"Rank {rank}/{total}: {meta['source']} (chunk {meta['chunk_index']}) — distance {dist:.4f}")

    print("\n--- For comparison, direct similarity check ---")
    # Pull the actual stored chunk text/embedding for contract_01 chunk 0 and
    # compare it directly, to rule out an indexing mixup.
    contract_result = collection.get(
        where={"source": "contract_01_acme_agreement.pdf"},
        include=["documents", "embeddings"],
    )
    print("Stored chunk text (first 300 chars):")
    print(contract_result["documents"][0][:300])


if __name__ == "__main__":
    main()
