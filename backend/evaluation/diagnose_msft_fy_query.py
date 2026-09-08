"""
diagnose_msft_fy_query.py
One-off diagnostic: checks where the chunk containing Microsoft's fiscal
year end date actually ranks for the query that failed in RAGAS eval,
and inspects what that chunk (if found at all) actually contains.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "retrieval"))
from hybrid_retriever import HybridRetriever


def main():
    query = "What was Microsoft's fiscal year end date for their most recent 10-K filing?"

    # Scope to just Microsoft's document to see how it's chunked
    retriever = HybridRetriever(source_filter="microsoft_10k_fy2026.pdf")
    print(f"Microsoft document has {len(retriever.ids)} total chunks.\n")

    results = retriever.search(query, top_k=10)
    print(f"Top 10 hybrid results for: {query!r}\n")
    for rank, r in enumerate(results, start=1):
        preview = r["text"][:200].replace("\n", " ")
        print(f"{rank}. [chunk {r['chunk_index']} | RRF {r['score']:.4f}] {preview}...\n")

    # Also check: does ANY chunk contain "fiscal year" + "June 30"?
    print("\n--- Searching all chunks for literal date mention ---")
    found = False
    for doc_text in retriever.documents:
        if "june 30" in doc_text.lower() or "fiscal year ended" in doc_text.lower():
            idx = retriever.documents.index(doc_text)
            meta = retriever.metadatas[idx]
            print(f"Found in chunk {meta['chunk_index']}: {doc_text[:300]}")
            found = True
    if not found:
        print("No chunk contains 'June 30' or 'fiscal year ended' literally.")


if __name__ == "__main__":
    main()
