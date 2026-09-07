"""
graph.py
Wires the four agent nodes into a single LangGraph pipeline:
retrieval -> extraction -> cross_check -> reporting

Run directly for a quick end-to-end smoke test once you have documents indexed.
"""

from langgraph.graph import StateGraph, END

from agents.state import PipelineState
from agents.retrieval_agent import retrieval_node
from agents.extraction_agent import extraction_node
from agents.cross_check_agent import cross_check_node
from agents.reporting_agent import reporting_node


def build_pipeline():
    graph = StateGraph(PipelineState)

    graph.add_node("retrieval", retrieval_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("cross_check", cross_check_node)
    graph.add_node("reporting", reporting_node)

    graph.set_entry_point("retrieval")
    graph.add_edge("retrieval", "extraction")
    graph.add_edge("extraction", "cross_check")
    graph.add_edge("cross_check", "reporting")
    graph.add_edge("reporting", END)

    return graph.compile()


if __name__ == "__main__":
    # Minimal smoke test — replace with real document loading once Phase 1/2 are done.
    pipeline = build_pipeline()

    initial_state: PipelineState = {
        "job_id": "test-001",
        "documents": [
            {"filename": "sample_invoice_1.pdf", "raw_text": "...", "chunks": ["..."]},
        ],
        "retrieved_context": {},
        "extracted": [],
        "flags": [],
        "report": None,
        "status": "queued",
    }

    final_state = pipeline.invoke(initial_state)
    print(final_state["report"])
