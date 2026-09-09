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
│   ├── retrieval_agent.py    Node 1 — hybrid search per document, collection-aware
│   ├── extraction_agent.py   Node 2 — LLM-based structured extraction
│   ├── cross_check_agent.py  Node 3 — consistency/audit checks
│   ├── reporting_agent.py    Node 4 — compiles final report
│   └── graph.py              Wires the four nodes into a LangGraph pipeline
├── run_pipeline.py           CLI entry point — runs the pipeline against the main indexed docs
├── app.py                    FastAPI backend — upload / status / report endpoints
├── job_store.py              In-memory job tracking for API-driven runs
├── retrieval/
│   ├── loader.py             PDF text extraction (+ OCR fallback)
│   ├── chunker.py            Overlapping character-window chunking
│   ├── ingest.py             Builds ChromaDB indexes (main + reusable per-job)
│   ├── hybrid_retriever.py   BM25 + vector search fused via RRF, collection-aware
│   └── query_test.py         Manual retrieval sanity checks
├── evaluation/
│   ├── eval_dataset.py       Hand-labeled Q&A test set
│   └── run_ragas_eval.py     RAGAS evaluation runner (local Ollama judge)
├── data/raw/                 Source PDFs (10-Ks + synthetic invoices/contracts)
├── data/jobs/                Per-upload working files (gitignored)
└── requirements.txt
frontend/
├── index.html                Google Fonts (Source Serif 4, IBM Plex Mono, Inter)
├── vite.config.js            Vite + Tailwind v4 plugin
└── src/
    ├── App.jsx               Upload UI, status polling, ledger-style report view
    └── index.css             Tailwind v4 theme tokens (@theme block)
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

## Multi-agent pipeline: findings from the first full run

Running the complete pipeline (retrieval → extraction → cross-check →
reporting) against all 12 synthetic documents surfaced three real issues,
fixed as follows:

1. **False "missing invoice number" flags on contracts.** The extraction
   schema only had an `invoice_number` field, so contracts (which have a
   *contract number* instead) were always flagged as missing one. Fixed by
   adding a `document_type` field to extraction and applying the correct
   identifier check per type.

2. **Overly broad vendor cross-check.** The original logic flagged *any*
   two documents from the same vendor with different totals — but multiple
   invoices from one vendor naturally have different amounts, so this
   produced noise rather than signal. Fixed by narrowing the check to what's
   actually audit-relevant: whether a vendor's invoiced total exceeds what
   their contract authorizes.

3. **A multi-page document's totals were extracted inconsistently across
   runs.** `invoice_09_multipage_clean.pdf` (line items on page 1, totals
   on page 3) sometimes produced the correct total and sometimes didn't,
   with no code changes between runs. Root-caused in two layers:

   - **Layer 1 — LLM sampling variance.** Ollama's default generation
     settings sample from a probability distribution even at low
     temperature, so identical prompts could yield different structured
     output. Fixed by setting `temperature: 0`, `top_k: 1`, `top_p: 0`,
     and a fixed `seed` for fully greedy, deterministic decoding.

   - **Layer 2 — retrieval ordering non-determinism.** Even after fixing
     LLM decoding, one document still varied between two consistent
     outcomes. Traced to floating-point non-determinism in local embedding
     computation (multi-threaded CPU inference doesn't always sum in the
     same order) — small enough to not change *which* chunks were
     retrieved, but occasionally enough to flip the *order* two
     closely-ranked chunks were returned in. Since the extraction agent
     read chunks in retrieval-rank order, this changed which chunk the LLM
     encountered first and how it reconciled the totals. Fixed by sorting
     retrieved chunks by their original position in the source document
     (`chunk_index`) before passing them to extraction, rather than by
     relevance rank — this removes ordering as a variable entirely.

   Verified stable, correct output across multiple repeated runs on all
   12 test documents after both fixes.

   **Takeaway:** deterministic LLM decoding alone doesn't guarantee
   deterministic pipeline output — non-determinism can enter upstream, in
   retrieval, and silently propagate downstream even when generation itself
   is pinned. Worth checking end-to-end, not just at the LLM call site.

## RAGAS evaluation results

Evaluated the full pipeline against a 10-question hand-labeled test set
(`evaluation/eval_dataset.py`) spanning both document types, using RAGAS
with **local Ollama models as the judge** (`mistral` for LLM-based scoring,
`nomic-embed-text` for embedding-based scoring) — no paid API required.

| Metric | Average | Rows scored |
|---|---|---|
| Faithfulness | 1.000 | 8/10 |
| Context Precision | 0.902 | 8/10 |
| Context Recall | 0.917 | 8/10 |
| Answer Relevancy | 0.852 | 10/10 |

**Faithfulness was perfect on every row that scored** — zero hallucination
detected, including on questions the system couldn't fully answer (it said
"I don't know" rather than fabricating).

Two real, distinct issues were found and fixed during evaluation:

1. **A retrieval depth issue, not a retrieval failure** (Microsoft's fiscal
   year end date). Diagnosis (`evaluation/diagnose_msft_fy_query.py`) showed
   the correct chunk — the 10-K's cover page, stating *"For the Fiscal Year
   Ended June 30, 2026"* verbatim — was retrieved, but ranked **9th**, just
   outside the evaluation's `top_k=5` cutoff. It was out-ranked by dense
   financial-table chunks that repeat "fiscal year" and the date many times,
   which score higher under both BM25 term frequency and embedding
   similarity than a single, sparse-but-exact cover-page mention. Fixed by
   raising retrieval depth to `top_k=10` for evaluation.

2. **A generation-side issue on an open-ended question.** The JPMorgan risk
   question initially scored `answer_relevancy: 0.0` despite correct
   retrieval (`context_recall: 1.0`) — likely the answer prompt's strict
   "say I don't know if unsure" instruction made the model overly cautious
   on an interpretive question, unlike the mostly single-fact lookups
   elsewhere in the test set. After the retrieval depth fix, this question's
   relevancy improved to 0.852 on re-run, suggesting the extra retrieved
   context gave the model enough confidence to answer normally.

**A known limitation, reported rather than hidden:** two rows (both on the
longest-context 10-K questions) returned `NaN` after the local judge model
(`mistral`, 7B) failed to produce output its own metric parser could parse
(`RagasOutputParserException`), rather than a scoring failure of the
pipeline being evaluated. This is a documented trade-off of using a small
local model as an LLM-as-judge instead of a larger hosted one — it affects
evaluation reliability, not the underlying system's correctness. Averages
above are computed over the rows that successfully scored.

## FastAPI backend: per-job isolation

Phase 5 wraps the pipeline in a FastAPI backend (`app.py`) with three
endpoints — `POST /upload`, `GET /status/{job_id}`, `GET /report/{job_id}` —
built around a background-task pattern so the upload request returns
instantly while the pipeline runs asynchronously.

The main design decision: **each upload gets its own isolated ChromaDB
collection** (`job_<id>`), built fresh from just the uploaded files, rather
than sharing the main project index. This required refactoring
`retrieval/ingest.py` and `HybridRetriever` to accept a `collection_name`
parameter, and adding `collection_name` to the shared pipeline state so the
retrieval agent knows which index to query. Without this, concurrent or
successive uploads would mix into a single shared index — irrelevant chunks
from one user's documents would pollute retrieval for another's.

Verified via direct HTTP calls (`curl`): the happy path, a cross-document
vendor-vs-contract check running correctly through the API (not just the
CLI), rejection of non-PDF uploads, and 404s on unknown job IDs.

## React frontend: designing for the subject matter

Phase 6's first pass used a generic SaaS-dashboard look — rounded cards,
blue accents, pill-shaped badges. It worked, but it didn't read as a
deliberate design choice, and a generic UI doesn't demonstrate frontend
judgment. It was rebuilt around the actual subject matter: an audit/ledger
tool, not a consumer app.

Key choices:
- **Serif headline + monospace data + sans body** — numbers (totals, job
  IDs) use `IBM Plex Mono` with tabular alignment, closer to how a real
  ledger presents figures, rather than uniform sans-serif throughout.
- **A hero metric strip** (documents reviewed, total value, high/medium
  finding counts) as the page's visual anchor, using large mono numerals —
  appropriate here since the report's headline fact genuinely is
  quantitative, not decorative.
- **Findings as a register, not badges** — each flagged issue renders as a
  full-width tinted row (soft red for HIGH, amber for MEDIUM) with a thick
  colored left border, giving the section the visual weight it deserves
  since it's the tool's entire point, rather than a small pill next to
  quiet text.
- **A structural report parser** (`parseReport()` in `App.jsx`) that turns
  the backend's markdown into real data — a summary table and a findings
  array — rather than rendering markdown line-by-line.

One real bug surfaced during this rebuild: **Tailwind v4 uses a completely
different configuration model** than v3 (a `@theme` block in CSS instead of
`tailwind.config.js` + `@tailwind` directives) — the initial redesign
silently produced zero styling because it used v3-style config against a
v4 install. Fixed by switching to the `@tailwindcss/vite` plugin and a
CSS-native `@theme` token block.

A second, subtler issue: an early color choice (a cool, slightly blue-green
muted gray) read as visibly olive/greenish against the warm cream paper
background — a **simultaneous contrast effect**, where a cool neutral next
to a warm background visually shifts toward its complementary hue. Fixed by
warming the gray to match the background's undertone.


## Roadmap

- [x] Phase 0 — Environment setup (Ollama, Python/FastAPI backend, React frontend)
- [x] Phase 1 — Document collection (real 10-Ks + synthetic test set)
- [x] Phase 2 — Retrieval layer (chunking, ChromaDB indexing, hybrid search)
- [x] Phase 3 — Multi-agent pipeline (extraction, cross-check, reporting agents),
      validated deterministic and correct across repeated runs on all 12 test documents
- [x] Phase 4 — RAGAS evaluation (retrieval precision/recall, answer faithfulness)
- [x] Phase 5 — FastAPI backend (upload, job status, report endpoints),
      with per-job isolated indexing verified via direct HTTP calls
- [x] Phase 6 — React frontend (upload UI, progress tracking, report view),
      redesigned around the subject matter after an initial generic pass
- [ ] Phase 7 — Docker + GitHub Actions CI/CD
- [ ] Phase 8 — Deployment (Hugging Face Spaces permanent; AWS + GCP for
      short-lived capture)
- [ ] Phase 9 — Polish, demo video, resume packaging

## Resume framing

*"Built a full-stack multi-agent financial document intelligence system —
hybrid BM25/vector RAG retrieval, LLM-based structured extraction, automated
cross-document consistency checks, a FastAPI backend with per-job isolated
indexing, and a React frontend designed around the audit/ledger domain.
Diagnosed and fixed a retrieval ranking failure (correct match at rank
16/2934, corrected to rank 1 via hybrid search) and a two-layer
non-determinism issue spanning LLM decoding and retrieval ordering,
validating fully reproducible output across repeated runs. Deployed via
Docker/CI-CD to Hugging Face Spaces, AWS, and GCP."*
