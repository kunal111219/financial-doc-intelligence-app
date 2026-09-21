from typing import TypedDict


class DocumentRecord(TypedDict):
    filename: str
    raw_text: str
    chunks: list[str]


class Flag(TypedDict):
    filename: str
    issue: str
    severity: str


class PipelineState(TypedDict):
    job_id: str
    collection_name: str
    documents: list[DocumentRecord]
    retrieved_context: dict[str, list[str]]
    extracted: list[dict]
    flags: list[Flag]
    report: str | None
    status: str
