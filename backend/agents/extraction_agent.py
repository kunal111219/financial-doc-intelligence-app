"""
extraction_agent.py
Node 2: Takes each document's retrieved context and asks a local LLM
(via Ollama) to pull it into a strict structured schema.

Handles three document types with different relevant fields:
- invoice: vendor, invoice number, amounts (subtotal/tax/total)
- contract: vendor, contract number, contract value, clauses
- financial_filing (e.g. a 10-K): company name, fiscal year, and the core
  financial-statement figures needed for an accounting-identity check
  (total assets, total liabilities, stockholders' equity, revenue, net
  income) — added specifically so filings get a real extraction path
  instead of being forced into the invoice schema, which previously
  produced meaningless "missing total amount" flags on every 10-K.
"""

import json
import ollama

from agents.state import PipelineState

MAX_CONTEXT_CHARS = 8000  # caps prompt length sent to the local model — a long,
                          # information-dense prompt (e.g. many 10-K chunks) was
                          # observed to make the model abandon the JSON schema
                          # entirely in favor of a free-text summary; capping
                          # context length keeps the model reliably on-schema

EXTRACTION_PROMPT = """You are a data extraction engine. You respond with ONLY a single JSON object
and nothing else — no summary, no explanation, no prose before or after it.

Extract the following fields from the document excerpt below. Use null for
anything not found.

{{
  "document_type": "invoice" or "contract" or "financial_filing" or "unknown",
  "vendor_name": string or null,
  "invoice_number": string or null,     // only applies to invoices
  "contract_number": string or null,    // only applies to contracts
  "dates": {{"invoice_date": string or null, "due_date": string or null, "effective_date": string or null}},
  "amounts": {{"subtotal": number or null, "tax": number or null, "total": number or null}},
  "clauses": [string],   // any notable obligations, penalties, or terms found

  "financials": {{        // only applies to financial_filing documents (e.g. a 10-K)
    "company_name": string or null,
    "fiscal_year_end": string or null,
    "total_revenue": number or null,
    "net_income": number or null,
    "total_assets": number or null,
    "total_liabilities": number or null,
    "stockholders_equity": number or null
  }}
}}

Rules:
- Respond with the JSON object only. Your entire response must start with {{ and end with }}.
- If this is a summary/totals page, use the EXPLICITLY STATED subtotal, tax, and
  total values as written — do not recompute or estimate them.
- If this is a financial filing (10-K, annual report), report financial-statement
  figures in the same units as stated in the document, using the most recent
  fiscal year's figures if multiple years are shown.

DOCUMENT EXCERPT:
---
{context}
---
"""


def extraction_node(state: PipelineState) -> PipelineState:
    """LangGraph node: populates state['extracted'] from retrieved_context."""
    state["status"] = "extracting"
    extracted = []

    for filename, chunks in state["retrieved_context"].items():
        context_text = "\n".join(chunks)[:MAX_CONTEXT_CHARS]

        response = ollama.generate(
            model="mistral",
            prompt=EXTRACTION_PROMPT.format(context=context_text),
            options={"temperature": 0, "top_k": 1, "top_p": 0, "seed": 42},
        )

        raw = response["response"].strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {
                "document_type": "unknown", "vendor_name": None,
                "invoice_number": None, "contract_number": None,
                "dates": {}, "amounts": {}, "clauses": [], "financials": {},
            }

        data["filename"] = filename
        extracted.append(data)

    state["extracted"] = extracted
    return state
