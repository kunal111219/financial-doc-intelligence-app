"""
run_pipeline.py
The real Phase 3 entry point — runs the full LangGraph pipeline
(retrieval -> extraction -> cross_check -> reporting) against whatever
documents are actually indexed in ChromaDB (via retrieval/ingest.py),
instead of the fake dummy state used in agents/graph.py's smoke test.

Usage (from backend/):
    python run_pipeline.py
"""

import os
import sys
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__), "retrieval"))
sys.path.append(os.path.dirname(__file__))

import chromadb
from agents.graph import build_pipeline
from agents.state import PipelineState

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")
COLLECTION_NAME = "financial_docs"


def get_indexed_filenames() -> list[str]:
    """Returns the unique list of source filenames currently indexed."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)
    all_data = collection.get(include=["metadatas"])
    sources = sorted({m["source"] for m in all_data["metadatas"]})
    return sources


def run(filenames: list[str] | None = None):
    """
    filenames: optional list to restrict the run to specific documents
    (e.g. just the synthetic invoices for a fast test run). Defaults to
    everything indexed.
    """
    if filenames is None:
        filenames = get_indexed_filenames()

    print(f"Running pipeline on {len(filenames)} documents:")
    for f in filenames:
        print(f"  - {f}")
    print()

    pipeline = build_pipeline()

    initial_state: PipelineState = {
        "job_id": str(uuid.uuid4())[:8],
        "documents": [{"filename": f, "raw_text": "", "chunks": []} for f in filenames],
        "retrieved_context": {},
        "extracted": [],
        "flags": [],
        "report": None,
        "status": "queued",
    }

    final_state = pipeline.invoke(initial_state)

    print("=" * 60)
    print(final_state["report"])
    print("=" * 60)

    return final_state


if __name__ == "__main__":
    # Start with just the synthetic invoices/contracts first — much faster
    # than running the full pipeline against the 10-Ks, and this is where
    # the extraction/cross-check logic actually gets exercised.
    synthetic_docs = [
        "invoice_01_clean_acme.pdf",
        "invoice_02_clean_bluewave.pdf",
        "invoice_03_error_acme.pdf",
        "invoice_04_missing_number.pdf",
        "invoice_05_clean_greenfield.pdf",
        "contract_01_acme_agreement.pdf",
        "invoice_06_acme_mismatch.pdf",
        "contract_02_bluewave_agreement.pdf",
        "invoice_07_clean_usd_vendor.pdf",
        "invoice_08_error_linesum.pdf",
        "invoice_09_multipage_clean.pdf",
        "invoice_10_multipage_error.pdf",
    ]
    run(filenames=synthetic_docs)
