"""
job_store.py
Simple in-memory job tracker. Fine for a portfolio-scale project running a
single process — a production version would use Redis or a database instead
so job state survives restarts and works across multiple worker processes.
"""

from typing import Optional, TypedDict
from threading import Lock


class JobRecord(TypedDict):
    job_id: str
    status: str            # "uploaded" | "indexing" | "running" | "done" | "error"
    filenames: list[str]
    report: Optional[str]
    error: Optional[str]


_jobs: dict[str, JobRecord] = {}
_lock = Lock()


def create_job(job_id: str, filenames: list[str]) -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "uploaded",
            "filenames": filenames,
            "report": None,
            "error": None,
        }


def update_status(job_id: str, status: str) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = status


def set_result(job_id: str, report: str) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["report"] = report


def set_error(job_id: str, error: str) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = error


def get_job(job_id: str) -> Optional[JobRecord]:
    with _lock:
        return _jobs.get(job_id)
