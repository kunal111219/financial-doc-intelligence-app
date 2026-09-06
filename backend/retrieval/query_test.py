"""
query_test.py
Quick manual sanity check after running ingest.py — now using hybrid
BM25 + vector search instead of vector-only, so this reflects what the
actual retrieval agent will return in the pipeline.

Usage:
    python retrieval/query_test.py
"""

from hybrid_retriever import HybridRetriever

TEST_QUERIES = [
    "What was the total revenue reported?",
    "invoice number and total amount due",
    "penalty clause for late payment",
    "risk factors related to competition",
]


def run_test_queries():
    retriever = HybridRetriever()  # no source_filter — searches across all documents
    print(f"Collection has {len(retriever.ids)} chunks indexed.\n")

    for query in TEST_QUERIES:
        print(f"Query: {query!r}")
        for rank, r in enumerate(retriever.search(query, top_k=3), start=1):
            preview = r["text"][:120].replace("\n", " ")
            print(f"  {rank}. [{r['source']} | chunk {r['chunk_index']} | RRF {r['score']:.4f}] {preview}...")
        print()


if __name__ == "__main__":
    run_test_queries()