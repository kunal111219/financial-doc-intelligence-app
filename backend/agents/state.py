"""
state.py
The shared state object that flows through every node in the LangGraph pipeline.
Each agent reads what it needs and writes its output back into this same object.
"""

from typing import TypedDict, List, Dict, Optional


class DocumentRecord(TypedDict):
    filename: str
    raw_text: str
    chunks: List[str]


class ExtractedData(TypedDict):
    filename: str
    vendor_name: Optional[str]
    invoice_number: Optional[str]
    dates: Dict[str, Optional[str]]
    amounts: Dict[str, Optional[float]]
    clauses: List[str]


class Flag(TypedDict):
    filename: str
    issue: str
    severity: str  # "low" | "medium" | "high"


class PipelineState(TypedDict):
    job_id: str
    collection_name: str                      # which ChromaDB collection to search — allows API jobs to use an isolated per-job index
    documents: List[DocumentRecord]          # filled by ingestion, read by retrieval agent
    retrieved_context: Dict[str, List[str]]   # filled by retrieval agent, keyed by filename
    extracted: List[ExtractedData]            # filled by extraction agent
    flags: List[Flag]                         # filled by cross-check agent
    report: Optional[str]                     # filled by reporting agent
    status: str                               # "retrieving" | "extracting" | "checking" | "reporting" | "done"
