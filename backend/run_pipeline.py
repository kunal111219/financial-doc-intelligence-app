"""
run_pipeline.py
The real Phase 3 entry point — runs the full LangGraph pipeline
(retrieval -> extraction -> cross_check -> reporting) against whatever
documents are actually indexed in ChromaDB (via retrieval/ingest.py),
instead of the fake dummy state used in agents/graph.py's smoke test.

By default, runs against every document currently indexed — no filenames
are hardcoded. Pass a substring filter to run a subset instead (useful
since the 10-Ks are slow to process one at a time on local CPU inference).

Usage (from backend/):
    python run_pipeline.py                # run everything indexed
    python run_pipeline.py invoice         # only filenames containing "invoice"
    python run_pipeline.py 10k             # only filenames containing "10k"
    python run_pipeline.py --list          # just show what's indexed, don't run
"""

import os
import sys
import uuid
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), "retrieval"))
sys.path.append(os.path.dirname(__file__))

import chromadb
from agents.graph import build_pipeline
from agents.state import PipelineState

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")
COLLECTION_NAME = "financial_docs"


def get_indexed_filenames(name_contains: str | None = None) -> list[str]:
    """
    Returns the unique list of source filenames currently indexed,
    optionally filtered to those whose filename contains name_contains
    (case-insensitive).
    """
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)
    all_data = collection.get(include=["metadatas"])
    sources = sorted({m["source"] for m in all_data["metadatas"]})

    if name_contains:
        needle = name_contains.lower()
        sources = [s for s in sources if needle in s.lower()]

    return sources


def run(filenames: list[str]):
    if not filenames:
        print("No matching documents found in the index. Run retrieval/ingest.py first,")
        print("or check your filter — nothing to process.")
        return None

    print(f"Running pipeline on {len(filenames)} documents:")
    for f in filenames:
        print(f"  - {f}")
    print()

    pipeline = build_pipeline()

    initial_state: PipelineState = {
        "job_id": str(uuid.uuid4())[:8],
        "collection_name": COLLECTION_NAME,
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
    parser = argparse.ArgumentParser(description="Run the full pipeline against indexed documents.")
    parser.add_argument("filter", nargs="?", default=None,
                         help="Optional substring — only run documents whose filename contains it.")
    parser.add_argument("--list", action="store_true",
                         help="List matching indexed documents without running the pipeline.")
    args = parser.parse_args()

    matched = get_indexed_filenames(args.filter)

    if args.list:
        print(f"{len(matched)} document(s) match:")
        for f in matched:
            print(f"  - {f}")
    else:
        run(matched)
