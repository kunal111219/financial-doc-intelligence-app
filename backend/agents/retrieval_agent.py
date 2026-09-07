"""
retrieval_agent.py
Node 1: For each document, retrieves the most relevant chunks for the fields
we care about (amounts, dates, parties, obligations) using hybrid BM25 +
vector search (see retrieval/hybrid_retriever.py). Hybrid search matters
here specifically because pure vector search under-ranked exact keyword
matches (e.g. "penalty clause") when a small number of relevant chunks
competed against thousands of unrelated ones — see project README for
the full writeup.

Chunks are sorted by their original position in the document (chunk_index)
before being passed downstream, rather than left in relevance-ranked order.
This was added after observing that a multi-page document's extracted
totals varied slightly across otherwise-deterministic runs — traced to
retrieval ranking order shifting slightly due to embedding-level floating
point non-determinism, which changed the order the extraction LLM saw the
document's chunks in. Presenting chunks in document order removes that
source of variation regardless of small fluctuations in relevance scoring.
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

        matches = {}  # id -> (chunk_index, text)
        for query in QUERY_TEMPLATES:
            for result in retriever.search(query, top_k=3):
                matches[result["id"]] = (result["chunk_index"], result["text"])

        # Sort by original document position, not retrieval relevance order —
        # keeps extraction input deterministic regardless of ranking jitter.
        ordered = sorted(matches.values(), key=lambda pair: pair[0])
        retrieved_context[doc_id] = [text for _, text in ordered]

    state["retrieved_context"] = retrieved_context
    return state
