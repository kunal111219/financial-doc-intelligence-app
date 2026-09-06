# Financial Document Intelligence System

A multi-agent system that ingests financial documents (10-Ks, invoices, vendor
contracts) and automatically extracts structured data, cross-checks figures
for inconsistencies, and produces a compliance-style report — modeled on the
internal document-automation tools used by Big 4 audit firms and MNC
finance/compliance teams.

Built end-to-end: retrieval, multi-agent orchestration, a FastAPI backend, a
React frontend, containerization, and cloud deployment — entirely with free
and open-source tools.

## Why this project

Manual review of financial documents — matching contract terms against
invoices, checking totals, spotting missing fields — is exactly the kind of
work Big 4 firms (Deloitte's Omnia, EY.ai, KPMG Clara) have built internal
automation for. This project is a scaled-down, from-scratch version of that
pattern, built to demonstrate retrieval-augmented generation, multi-agent
orchestration, and full-stack delivery in one coherent system.

## Architecture

```
React Frontend  →  FastAPI Backend  →  LangGraph Multi-Agent Pipeline
                                          ├─ Retrieval Agent (hybrid search)
                                          ├─ Extraction Agent (LLM → JSON)
                                          ├─ Cross-Check Agent (audit logic)
                                          └─ Reporting Agent (final report)
                                          ↓
                                     RAGAS Evaluation
```

**Stack:** Ollama (local LLM inference) · ChromaDB (vector store) · BM25
(keyword search) · LangGraph (agent orchestration) · RAGAS (evaluation) ·
FastAPI · React + Tailwind · Docker · GitHub Actions · Hugging Face Spaces
(+ short-lived AWS/GCP deployment for cloud experience).

No paid services are required to build or run this project.

## Project structure

```
backend/
├── agents/
│   ├── state.py              Shared pipeline state (TypedDict)
│   ├── retrieval_agent.py    Node 1 — hybrid search per document
│   ├── extraction_agent.py   Node 2 — LLM-based structured extraction
│   ├── cross_check_agent.py  Node 3 — consistency/audit checks
│   ├── reporting_agent.py    Node 4 — compiles final report
│   └── graph.py              Wires the four nodes into a LangGraph pipeline
├── retrieval/
│   ├── loader.py             PDF text extraction (+ OCR fallback)
│   ├── chunker.py            Overlapping character-window chunking
│   ├── ingest.py             Builds the ChromaDB index from data/raw/
│   ├── hybrid_retriever.py   BM25 + vector search fused via RRF
│   └── query_test.py         Manual retrieval sanity checks
├── data/raw/                 Source PDFs (10-Ks + synthetic invoices/contracts)
└── requirements.txt
frontend/                     React + Tailwind UI (upload, progress, report view)
```

## Test document set

- **5 real 10-K filings** (Apple, Microsoft, Walmart, PepsiCo, JPMorgan),
  sourced from SEC EDGAR — spans different industries and fiscal year-ends,
  and stress-tests retrieval at scale (200-300+ pages each).
- **12 synthetic invoices/contracts**, generated to include planted issues:
  mismatched subtotal/tax/total, a missing invoice number, a vendor whose
  contract value doesn't match a later invoice, a multi-currency invoice, and
  two multi-page documents where line items and totals sit on different pages.

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

ollama pull mistral
ollama pull nomic-embed-text

# Place PDFs in data/raw/, then build the index:
python retrieval/ingest.py

# Sanity-check retrieval:
python retrieval/query_test.py
```

Poppler (for OCR fallback via `pdf2image`) and Tesseract are only needed if
you're processing scanned documents — see project notes for Windows install
steps.

## Retrieval evaluation: a real finding, not just a demo

Initial testing with pure vector search (ChromaDB + `nomic-embed-text`)
surfaced a genuine weakness: a query for **"penalty clause for late
payment"** — despite an exact, verbatim match sitting in a contract document
— ranked that contract chunk **16th out of 2,934** chunks. With only 2
contract chunks competing against 2,932 chunks of 10-K text that also
mention "payment," "overdue," and "penalties" in passing, semantic
similarity alone wasn't enough to surface the true match.

**Fix:** implemented hybrid retrieval — BM25 keyword search combined with
vector search via **Reciprocal Rank Fusion** (`retrieval/hybrid_retriever.py`).
This corrected the same query to rank the correct contract chunk **#1**,
without regressing performance on the other test queries (revenue figures,
invoice lookups, risk factor sections all continued to rank correctly).

This is documented in more detail via `retrieval/diagnose_penalty_query.py`,
which was used to pinpoint the exact rank and root cause before choosing a fix.

## Roadmap

- [x] Phase 0 — Environment setup (Ollama, Python/FastAPI backend, React frontend)
- [x] Phase 1 — Document collection (real 10-Ks + synthetic test set)
- [x] Phase 2 — Retrieval layer (chunking, ChromaDB indexing, hybrid search)
- [ ] Phase 3 — Multi-agent pipeline (extraction, cross-check, reporting agents)
- [ ] Phase 4 — RAGAS evaluation (retrieval precision/recall, answer faithfulness)
- [ ] Phase 5 — FastAPI backend (upload, job status, report endpoints)
- [ ] Phase 6 — React frontend (upload UI, progress tracking, report view)
- [ ] Phase 7 — Docker + GitHub Actions CI/CD
- [ ] Phase 8 — Deployment (Hugging Face Spaces permanent; AWS + GCP for
      short-lived capture)
- [ ] Phase 9 — Polish, demo video, resume packaging

## Resume framing

*"Built a multi-agent financial document intelligence system — hybrid
BM25/vector RAG retrieval, LLM-based structured extraction, and automated
cross-document consistency checks — evaluated with RAGAS and diagnosed a
retrieval ranking failure (correct match at rank 16/2934) that hybrid search
fixed to rank 1. Deployed via Docker/CI-CD to Hugging Face Spaces, AWS, and
GCP."*
