"""
reporting_agent.py
Node 4: Compiles extracted data + flags into a final human-readable report.

Summary line format is kept consistent across document types
("Vendor: X, Total: Y") for compatibility with the frontend's report
parser (see frontend/src/App.jsx parseReport()) — for financial filings,
"Vendor" holds the company name and "Total" holds total assets with a
clarifying label, rather than introducing a second summary format.
"""

from agents.state import PipelineState
from agents.benford_analysis import analyze_totals, format_benford_section


def _format_amount(value):
    if value is None:
        return "—"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def reporting_node(state: PipelineState) -> PipelineState:
    """LangGraph node: populates state['report'] and marks the job done."""
    state["status"] = "reporting"

    lines = [f"# Financial Document Intelligence Report — Job {state['job_id']}\n"]
    lines.append(f"Documents processed: {len(state['extracted'])}\n")

    lines.append("## Summary\n")
    for record in state["extracted"]:
        doc_type = record.get("document_type", "unknown")

        if doc_type == "financial_filing":
            financials = record.get("financials") or {}
            entity = financials.get("company_name") or "Unknown company"
            amount_str = f"{_format_amount(financials.get('total_assets'))} (Total Assets)"
        else:
            amounts = record.get("amounts") or {}
            entity = record.get("vendor_name") or "Unknown"
            amount_str = _format_amount(amounts.get("total"))

        lines.append(f"- **{record['filename']}** — Vendor: {entity}, Total: {amount_str}")

    lines.append("\n## Flagged Issues\n")
    if not state["flags"]:
        lines.append("No issues flagged.")
    else:
        for flag in state["flags"]:
            lines.append(f"- [{flag['severity'].upper()}] {flag['filename']}: {flag['issue']}")

    invoice_totals = [
        (r.get("amounts") or {}).get("total")
        for r in state["extracted"]
        if r.get("document_type") == "invoice"
    ]
    invoice_totals = [t for t in invoice_totals if t is not None]
    benford_result = analyze_totals(invoice_totals)
    lines.append("\n")
    lines.append(format_benford_section(benford_result))

    state["report"] = "\n".join(lines)
    state["status"] = "done"
    return state
