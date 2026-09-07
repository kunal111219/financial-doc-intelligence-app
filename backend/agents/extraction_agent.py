"""
extraction_agent.py
Node 2: Takes each document's retrieved context and asks a local LLM
(via Ollama) to pull it into a strict structured schema.

Includes a document_type field (invoice vs contract) so downstream
cross-check logic can apply the right rules to each — a contract has no
invoice number, so treating every document as an invoice produced false
"missing invoice number" flags on contracts.
"""

import json
import ollama

from agents.state import PipelineState

EXTRACTION_PROMPT = """Extract the following fields from this document excerpt as JSON only
(no markdown fences, no commentary). Use null for anything not found.

{{
  "document_type": "invoice" or "contract" or "unknown",
  "vendor_name": string or null,
  "invoice_number": string or null,     // only applies to invoices
  "contract_number": string or null,    // only applies to contracts
  "dates": {{"invoice_date": string or null, "due_date": string or null, "effective_date": string or null}},
  "amounts": {{"subtotal": number or null, "tax": number or null, "total": number or null}},
  "clauses": [string]   // any notable obligations, penalties, or terms found
}}

Important: if this is a summary/totals page, use the EXPLICITLY STATED subtotal,
tax, and total values as written — do not recompute or estimate them from other
sections if a clear final summary of charges is present in the excerpt.

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
        context_text = "\n".join(chunks)

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
                "dates": {}, "amounts": {}, "clauses": [],
            }

        data["filename"] = filename
        extracted.append(data)

    state["extracted"] = extracted
    return state
