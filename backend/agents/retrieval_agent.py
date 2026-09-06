"""
retrieval_agent.py
Node 1: For each document, retrieves the most relevant chunks for the fields
we care about (amounts, dates, parties, obligations) using hybrid BM25 +
vector search (see retrieval/hybrid_retriever.py). Hybrid search matters
here specifically because pure vector search under-ranked exact keyword
matches (e.g. "penalty clause") when a small number of relevant chunks
competed against thousands of unrelated ones — see project README for
the full writeup.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "retrieval"))
from hybrid_retriever import HybridRetriever  # noqa: E402

from agents.state import PipelineState

QUERY_TEMPLATES = [
    "invoice number, date, and total amount",
    "vendor or party names and contract terms",
    "payment obligations, due dates, and penalties",
]


def retrieval_node(state: PipelineState) -> PipelineState:
    """LangGraph node: populates state['retrieved_context'] per document."""
    state["status"] = "retrieving"
    retrieved_context = {}

    for doc in state["documents"]:
        doc_id = doc["filename"]

        # Scope retrieval to just this document's chunks — both for BM25
        # (avoids other documents' vocabulary skewing scores) and vector search.
        retriever = HybridRetriever(source_filter=doc_id)

        matches = {}
        for query in QUERY_TEMPLATES:
            for result in retriever.search(query, top_k=3):
                matches[result["id"]] = result["text"]

        retrieved_context[doc_id] = list(matches.values())

    state["retrieved_context"] = retrieved_context
    return state
