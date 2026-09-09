"""
app.py
Phase 5 entry point — FastAPI backend wrapping the LangGraph pipeline.

Endpoints:
  POST /upload            — accepts one or more PDFs, kicks off processing, returns job_id
  GET  /status/{job_id}   — current job status
  GET  /report/{job_id}   — final report (once status == "done")

Each upload gets its own isolated ChromaDB collection (named job_<id>) so
concurrent/successive uploads never mix with each other or with the main
project index used by run_pipeline.py and the RAGAS evaluation.

Run with:
    uvicorn app:app --reload
"""

import os
import sys
import uuid
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.join(os.path.dirname(__file__), "retrieval"))
sys.path.append(os.path.dirname(__file__))

from retrieval.loader import extract_text_native
from retrieval.ingest import index_documents
from agents.graph import build_pipeline
from agents.state import PipelineState
import job_store

app = FastAPI(title="Financial Document Intelligence API")

# Allow the React dev server to call this API during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS_DIR = os.path.join(os.path.dirname(__file__), "data", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)


def process_job(job_id: str, filepaths: list[str]):
    """Runs in the background: extract text, index, run the full pipeline."""
    try:
        job_store.update_status(job_id, "indexing")

        documents = {}
        for path in filepaths:
            filename = os.path.basename(path)
            documents[filename] = extract_text_native(path)

        collection_name = f"job_{job_id}"
        index_documents(documents, collection_name, fresh=True)

        job_store.update_status(job_id, "running")

        pipeline = build_pipeline()
        initial_state: PipelineState = {
            "job_id": job_id,
            "collection_name": collection_name,
            "documents": [{"filename": f, "raw_text": "", "chunks": []} for f in documents.keys()],
            "retrieved_context": {},
            "extracted": [],
            "flags": [],
            "report": None,
            "status": "queued",
        }

        final_state = pipeline.invoke(initial_state)
        job_store.set_result(job_id, final_state["report"])

    except Exception as e:
        job_store.set_error(job_id, str(e))


@app.post("/upload")
async def upload_documents(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    job_id = str(uuid.uuid4())[:8]
    job_folder = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_folder, exist_ok=True)

    filepaths = []
    filenames = []
    for upload in files:
        if not upload.filename.lower().endswith(".pdf"):
            continue
        dest_path = os.path.join(job_folder, upload.filename)
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(upload.file, f)
        filepaths.append(dest_path)
        filenames.append(upload.filename)

    if not filepaths:
        raise HTTPException(status_code=400, detail="No valid PDF files provided")

    job_store.create_job(job_id, filenames)
    background_tasks.add_task(process_job, job_id, filepaths)

    return {"job_id": job_id, "filenames": filenames, "status": "uploaded"}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": job["status"], "filenames": job["filenames"]}


@app.get("/report/{job_id}")
async def get_report(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=f"Job failed: {job['error']}")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Job not finished yet (status: {job['status']})")
    return {"job_id": job_id, "report": job["report"]}


@app.get("/")
async def root():
    return {"message": "Financial Document Intelligence API is running"}
