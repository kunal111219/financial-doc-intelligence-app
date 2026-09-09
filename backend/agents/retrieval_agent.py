"""
retrieval_agent.py
Node 1: For each document, retrieves the most relevant chunks for the fields
we care about (amounts, dates, parties, obligations) using hybrid BM25 +
vector search (see retrieval/hybrid_retriever.py).

Reads state["collection_name"] so API-driven jobs can point at their own
isolated per-job ChromaDB collection (built fresh from just the uploaded
files) without disturbing the main project index used for run_pipeline.py
and the RAGAS evaluation. Falls back to the default collection if not set,
so existing scripts (run_pipeline.py) keep working unchanged.

Chunks are sorted by their original position in the document (chunk_index)
before being passed downstream, rather than left in relevance-ranked order
— see project README for why (a two-layer non-determinism finding from
Phase 3).
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "retrieval"))
from hybrid_retriever import HybridRetriever, COLLECTION_NAME  # noqa: E402

from agents.state import PipelineState

QUERY_TEMPLATES = [
    "invoice number, date, and total amount",
    "vendor or party names and contract terms",
    "payment obligations, due dates, and penalties",
]


def retrieval_node(state: PipelineState) -> PipelineState:
    """LangGraph node: populates state['retrieved_context'] per document."""
    state["status"] = "retrieving"
    collection_name = state.get("collection_name") or COLLECTION_NAME
    retrieved_context = {}

    for doc in state["documents"]:
        doc_id = doc["filename"]

        retriever = HybridRetriever(source_filter=doc_id, collection_name=collection_name)

        matches = {}  # id -> (chunk_index, text)
        for query in QUERY_TEMPLATES:
            for result in retriever.search(query, top_k=3):
                matches[result["id"]] = (result["chunk_index"], result["text"])

        ordered = sorted(matches.values(), key=lambda pair: pair[0])
        retrieved_context[doc_id] = [text for _, text in ordered]

    state["retrieved_context"] = retrieved_context
    return state
