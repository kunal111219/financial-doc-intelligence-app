# Financial Document Intelligence System

A multi-agent system that ingests financial documents (10-Ks, invoices,
vendor contracts) and automatically extracts structured data, cross-checks
figures for inconsistencies, and produces a compliance-style report.

Built end-to-end: retrieval, multi-agent orchestration, a FastAPI backend, a
React frontend, and a set of real audit/forensic-accounting checks — entirely
with free and open-source tools.

## What this actually is (an honest scope note)

Early on this project was pitched as "a Big 4-style audit tool." That
framing oversold it. What's actually built and validated is narrower and
more honest: **a document consistency-checking system covering two real,
correctly-scoped audit procedures** —

1. **AP/invoice reconciliation** — does an invoice's math check out, does it
   match its contract, is it a duplicate, does its numbering sequence make
   sense. This maps to real "vouching and tracing" work.
2. **Financial statement consistency checking** — does a 10-K's own reported
   figures satisfy the fundamental accounting identity
   (Assets = Liabilities + Equity). This maps to real "analytical
   procedures" auditors perform.

Real Big 4/MNC audit platforms operate at a different scale entirely — full
general-ledger population testing across millions of transactions, direct
ERP integration, ML-driven risk-based sampling. This project doesn't claim
that scale. It claims, and has evidence for, correctly implementing the
document-level slice of that work, using comparable architecture (RAG +
multi-agent orchestration), and being honest about where extraction
accuracy — not the underlying logic — is the limiting factor.

## Architecture

```
React Frontend  →  FastAPI Backend  →  LangGraph Multi-Agent Pipeline
                                          ├─ Retrieval Agent (hybrid search)
                                          ├─ Extraction Agent (LLM → JSON)
                                          ├─ Cross-Check Agent (audit logic)
                                          └─ Reporting Agent (report + stats)
                                          ↓
                                     RAGAS Evaluation
```

**Stack:** Ollama (local LLM inference) · ChromaDB (vector store) · BM25
(keyword search) · LangGraph (agent orchestration) · RAGAS (evaluation) ·
scipy (statistical testing) · FastAPI · React + Tailwind v4 · Docker (planned)

No paid services are required to build or run this project.

## Project structure

```
backend/
├── agents/
│   ├── state.py               Shared pipeline state (TypedDict)
│   ├── retrieval_agent.py     Node 1 — hybrid search, collection-aware
│   ├── extraction_agent.py    Node 2 — LLM-based structured extraction
│   │                          (invoice / contract / financial_filing schemas)
│   ├── cross_check_agent.py   Node 3 — all audit/consistency checks
│   ├── benford_analysis.py    Batch-level Benford's Law statistical test
│   ├── reporting_agent.py     Node 4 — compiles report + statistical section
│   └── graph.py               Wires the four nodes into a LangGraph pipeline
├── run_pipeline.py            CLI entry point — auto-discovers indexed docs,
│                              optional substring filter, no hardcoded lists
├── app.py                     FastAPI backend — upload / status / report
├── job_store.py                In-memory job tracking for API-driven runs
├── diagnose_10k_extraction.py  One-off diagnostic — raw model output before parsing
├── tests/
│   └── test_cross_check_agent.py  18 pytest tests — every cross-check rule
├── retrieval/
│   ├── loader.py               PDF text extraction (+ OCR fallback)
│   ├── chunker.py               Overlapping character-window chunking
│   ├── ingest.py                 Builds ChromaDB indexes (main + per-job)
│   ├── hybrid_retriever.py      BM25 + vector search fused via RRF
│   ├── query_test.py             Manual retrieval sanity checks
│   └── diagnose_penalty_query.py One-off retrieval-rank diagnostic
├── evaluation/
│   ├── eval_dataset.py           Hand-labeled Q&A test set
│   ├── run_ragas_eval.py         RAGAS evaluation runner (local Ollama judge)
│   └── diagnose_msft_fy_query.py One-off retrieval-depth diagnostic
├── data/raw/                    Source PDFs (10-Ks + synthetic test set)
├── data/jobs/                   Per-upload working files (gitignored)
└── requirements.txt
frontend/
├── index.html                   Google Fonts (Source Serif 4, IBM Plex Mono, Inter)
├── vite.config.js                Vite + Tailwind v4 plugin
└── src/
    ├── App.jsx                   Upload UI, status polling, ledger-style report
    ├── reportParser.js           Extracted, unit-tested report-parsing logic
    ├── reportParser.test.js      10 Vitest tests — including 2 real regressions caught
    └── index.css                  Tailwind v4 theme tokens (@theme block)
```

## Test document set

- **5 real 10-K filings** (Apple, Microsoft, Walmart, PepsiCo, JPMorgan),
  sourced from SEC EDGAR — spans industries and fiscal year-ends, stress-tests
  retrieval at scale (200-300+ pages each) and the financial-filing extraction
  path.
- **13 synthetic invoices/contracts** with planted issues: mismatched
  subtotal/tax/total, a missing invoice number, a vendor whose contract value
  doesn't match a later invoice, a multi-currency invoice, two multi-page
  documents, a duplicate invoice, an invoice-number sequence gap, and a
  due-date-before-invoice-date error.
- **80 additional synthetic invoices**, log-uniformly distributed in amount
  (₹103 to ₹19.4 lakh) across 8 vendors with per-vendor sequential numbering
  — built specifically to give Benford's Law analysis a statistically
  meaningful sample.

## Retrieval evaluation: a real finding, not just a demo

Initial testing with pure vector search (ChromaDB + `nomic-embed-text`)
surfaced a genuine weakness: a query for **"penalty clause for late
payment"** — despite an exact, verbatim match sitting in a contract document
— ranked that contract chunk **16th out of 2,934** chunks, out-scored by
thousands of unrelated 10-K chunks that also mention "payment" or "overdue"
in passing.

**Fix:** hybrid retrieval — BM25 keyword search combined with vector search
via **Reciprocal Rank Fusion** (`retrieval/hybrid_retriever.py`). Corrected
the same query to rank the correct chunk **#1**, without regressing the
other test queries.

## Multi-agent pipeline: findings from the first full runs

1. **False "missing invoice number" flags on contracts** — fixed by adding a
   `document_type` field to extraction and applying the correct identifier
   check per type.
2. **Overly broad vendor cross-check** — narrowed from "any two totals differ"
   to the audit-relevant check: does an invoice exceed its own contract's
   authorized value.
3. **A multi-page document's totals were extracted inconsistently across
   runs**, with no code changes between runs. Root-caused in two layers:
   Ollama's default sampling (fixed via `temperature: 0, top_k: 1, top_p: 0,
   seed: 42`), and a subtler retrieval-ordering non-determinism from
   floating-point variance in local embedding computation (fixed by sorting
   retrieved chunks by document position, not relevance rank, before passing
   to extraction). **Takeaway:** deterministic LLM decoding alone doesn't
   guarantee deterministic pipeline output — non-determinism can enter
   upstream in retrieval and propagate downstream silently.

## RAGAS evaluation results

Evaluated against a 10-question hand-labeled test set spanning both document
types, using RAGAS with **local Ollama models as the judge** — no paid API.

| Metric | Average | Rows scored |
|---|---|---|
| Faithfulness | 1.000 | 8/10 |
| Context Precision | 0.902 | 8/10 |
| Context Recall | 0.917 | 8/10 |
| Answer Relevancy | 0.852 | 10/10 |

Two issues diagnosed and fixed during evaluation: a retrieval **depth** issue
(a correct chunk ranked 9th, outside `top_k=5`, fixed by raising depth to 10)
and a generation over-caution issue that resolved once retrieval improved.
One honestly-reported limitation: the local 7B judge model occasionally
failed to produce parseable output on the longest-context questions
(`RagasOutputParserException`, 2/10 rows) — a documented trade-off of local-
judge evaluation, not a flaw in the pipeline being evaluated.

## FastAPI backend: per-job isolation

`app.py` wraps the pipeline in `POST /upload`, `GET /status/{job_id}`,
`GET /report/{job_id}`, using a background-task pattern so uploads return
instantly. **Each upload gets its own isolated ChromaDB collection**
(`job_<id>`), built fresh from just the uploaded files, so concurrent or
successive uploads never mix. Verified via direct HTTP calls: happy path,
cross-document vendor-vs-contract check, non-PDF rejection, unknown-job 404s.

## React frontend: designing for the subject matter

The first pass used a generic SaaS-dashboard look. Rebuilt around the actual
subject matter — an audit/ledger tool, not a consumer app: serif headline +
monospace tabular data + sans body, a hero metric strip (documents reviewed,
total value, high/medium finding counts), and findings rendered as a tinted-
row register rather than badge pills. Two real bugs surfaced and fixed along
the way: a Tailwind v4 configuration mismatch (v3-style config silently
produced zero styling), and a **simultaneous contrast** color issue — a cool
muted gray read as visibly olive-green against the warm cream background,
fixed by warming the gray's undertone to match.

## Expanded audit checks: closing the "is this really an audit tool" gap

After the initial build, testing real 10-Ks through the pipeline surfaced
that extraction and cross-checking had only ever been designed around
invoices/contracts — every 10-K got flagged "missing total amount," a
meaningless result, since a 10-K has no single "total." This was a real
scope gap against the project's own pitch, not a documented boundary, and
was fixed by extending the pipeline to handle financial filings as a
genuinely different, correctly-checked document type, plus adding five
further real audit/forensic-accounting techniques.

**1. Financial statement identity check (Assets = Liabilities + Equity)**
Added a `financial_filing` extraction schema (company name, fiscal year,
revenue, net income, total assets/liabilities/equity) and the fundamental
accounting identity as a cross-check, with a 1% relative tolerance (filings
report in rounded millions/billions).

Along the way, a real extraction reliability issue surfaced: given a long,
complex, multi-type prompt against a dense 10-K excerpt, the local 7B model
**abandoned the JSON schema entirely** and wrote a free-text narrative
summary instead — confirmed by inspecting the raw model output directly
(`diagnose_10k_extraction.py`) rather than guessing from the parse failure.
Fixed with three changes: splitting merged retrieval queries into short,
literal phrases matching real financial-statement wording ("total assets,"
"total liabilities" instead of one combined query — the same insight as the
earlier BM25 fix), capping context at 8,000 characters, and a much more
forceful "respond with only the JSON object" instruction.

**Validated against real, independently verified figures**, not just
internal consistency:
- **Apple**: extracted Total Assets, Total Liabilities, and Stockholders'
  Equity all matched real published figures *exactly* — proof the check's
  logic is sound when retrieval surfaces the right chunk. (A separate,
  minor bug was also found this way: `total_revenue` was incorrectly
  duplicated from `total_assets` when revenue wasn't in the retrieved
  context, instead of correctly returning null.)
- **Walmart**: the identity check flagged a mismatch. Cross-referencing
  against Walmart's real reported total assets ($284.67B — which the
  extraction matched exactly) showed the flag was caused by an inaccurate
  liabilities/equity extraction, not a real accounting problem. This is an
  important, honestly-reported finding: **the check's logic can be entirely
  correct while still producing a false positive from upstream extraction
  error** — a real reason automated audit flags need human review before
  being trusted, not a flaw in the check design.

**2. Duplicate invoice detection** — same vendor, same total, invoice dates
within 3 days. Validated with a planted duplicate test case.

**3. Sequence gap detection** — flags missing invoice numbers per vendor.
Initially flagged *any* gap ≥1, which produced 58 low-value flags when
tested against the 80-document Benford batch — small gaps (voided invoices,
shared number pools) are normal in real business. Fixed in two stages:
raised the threshold to only flag gaps >5, then found the remaining ~37
flags traced to the Benford batch's own test-data design (a single global
invoice-number pool shared across 8 vendors, not a check design flaw) and
fixed the generator to give each vendor genuine per-vendor sequential
numbering. Final result: zero spurious flags on the 80-document batch, while
the original planted-gap test case (adjusted to skip 6 numbers, above the
new threshold) still correctly triggers.

**4. Date logic validation** — due date before invoice date. Validated with
a planted test case.

**5. Round-number / structuring detection** — flags invoice totals evenly
divisible by 10,000 as worth a second look. Initially applied to contracts
too, which produced false positives on both test contracts (negotiated
contract values are legitimately, commonly round — unlike individual
transaction totals). Fixed by scoping the check to invoices only.

**6. Benford's Law analysis** — a batch-level (not per-document) statistical
test: does the leading-digit distribution of invoice totals conform to
Benford's Law, using a proper chi-square goodness-of-fit test
(`scipy.stats.chisquare`). **Explicitly gated on sample size**
(`MIN_SAMPLE_SIZE = 30`) — below that, the report states plainly that no
statistical claim is being made, rather than showing a meaningless result.
Required generating a purpose-built 80-invoice batch with log-uniform
amounts (spanning ₹103 to ₹19.4 lakh) — the condition under which real
transaction data actually conforms to Benford's Law; a narrow range of
similar-magnitude amounts would not conform even for genuine data. Validated
result: chi-square = 6.31, p = 0.61, correctly concludes conformance for
data generated to conform.

## Testing

Manual validation throughout this project (planted-issue documents, checked
by eye against `run_pipeline.py` output) has now been turned into automated
regression suites on both ends:

- **Backend** (`backend/tests/test_cross_check_agent.py`, pytest) — 18 tests
  covering every cross-check rule: math reconciliation, type-scoped
  identifier checks, round-number scoping (invoice-only), date logic,
  duplicate detection, sequence-gap threshold tuning, vendor-vs-contract
  checks, and the financial-filing accounting identity (using Apple's real,
  independently verified figures as a fixture).
- **Frontend** (`frontend/src/reportParser.test.js`, Vitest) — 10 tests
  covering the report-parsing logic, including two real regressions found
  and fixed this session: `parseFloat` silently truncating comma-formatted
  totals (`"100,300.00"` → `100`) once the backend started comma-formatting
  amounts, and a mixed invoice/filing batch producing a meaningless blended
  "total value reviewed" figure by summing invoice thousands together with
  a filing's total assets in the billions. The parsing logic was extracted
  into `reportParser.js` specifically so it could be unit tested directly
  rather than only exercised through full component rendering. **The suite
  caught a third real bug on its first run against a different machine**:
  `toLocaleString(undefined, ...)` uses the runtime's system locale, so the
  same number formatted as `100,300.00` (Western grouping) in one
  environment and `1,00,300.00` (Indian lakh/crore grouping) in another —
  fixed by pinning the locale explicitly to `"en-US"` rather than leaving
  a financial report's number formatting dependent on the viewer's OS
  settings.

```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend
cd frontend && npm install -D vitest && npx vitest run
```

## Roadmap

- [x] Phase 0 — Environment setup
- [x] Phase 1 — Document collection (real 10-Ks + synthetic test set)
- [x] Phase 2 — Retrieval layer (chunking, ChromaDB indexing, hybrid search)
- [x] Phase 3 — Multi-agent pipeline, validated deterministic across repeated runs
- [x] Phase 3b — Expanded audit checks: financial-filing identity check
      (verified against real Apple/Walmart figures), duplicate detection,
      sequence-gap detection, date logic validation, round-number detection,
      and a properly sample-size-gated Benford's Law analysis
- [x] Phase 4 — RAGAS evaluation
- [x] Phase 5 — FastAPI backend with per-job isolated indexing
- [x] Phase 6 — React frontend, redesigned around the audit/ledger domain
- [ ] Phase 7 — Docker + GitHub Actions CI/CD
- [ ] Phase 8 — Deployment (Hugging Face Spaces permanent; AWS + GCP for
      short-lived resume-credential capture)
- [ ] Phase 9 — Polish, demo video, resume packaging

## Resume framing

*"Built a full-stack multi-agent financial document intelligence system —
hybrid BM25/vector RAG retrieval, LLM-based structured extraction across
invoice/contract and financial-filing schemas, and a set of real audit and
forensic-accounting checks (accounting-identity verification, duplicate and
sequence-gap detection, Benford's Law analysis with proper statistical
gating). Validated the financial-statement check against real, independently
verified SEC filing data, correctly diagnosing a false positive as an
extraction error rather than a logic flaw. Diagnosed and fixed a retrieval
ranking failure and a two-layer non-determinism issue spanning LLM decoding
and retrieval ordering. Backed by a 28-test automated regression suite
(pytest + Vitest) that caught two real bugs during development. Delivered
via a FastAPI backend with per-job isolated
indexing and a React frontend designed around the audit domain."*
