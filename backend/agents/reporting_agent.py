"""
reporting_agent.py
Node 4: Compiles extracted data + flags into a final human-readable report.
"""

from agents.state import PipelineState


def reporting_node(state: PipelineState) -> PipelineState:
    """LangGraph node: populates state['report'] and marks the job done."""
    state["status"] = "reporting"

    lines = [f"# Financial Document Intelligence Report — Job {state['job_id']}\n"]
    lines.append(f"Documents processed: {len(state['extracted'])}\n")

    lines.append("## Summary\n")
    for record in state["extracted"]:
        amounts = record.get("amounts") or {}
        lines.append(
            f"- **{record['filename']}** — Vendor: {record.get('vendor_name', 'Unknown')}, "
            f"Total: {amounts.get('total', '—')}"
        )

    lines.append("\n## Flagged Issues\n")
    if not state["flags"]:
        lines.append("No issues flagged.")
    else:
        for flag in state["flags"]:
            lines.append(f"- [{flag['severity'].upper()}] {flag['filename']}: {flag['issue']}")

    state["report"] = "\n".join(lines)
    state["status"] = "done"
    return state
