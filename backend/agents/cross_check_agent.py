"""
cross_check_agent.py
Node 3: This is the "audit" logic. Compares extracted figures within and
across documents and raises flags.

Two fixes applied after the first full pipeline run surfaced false positives:
1. "Missing invoice number" no longer fires on contracts (they have a
   contract_number instead — checking the wrong field was a schema gap,
   not a real issue with the documents).
2. Vendor comparison no longer flags every pair of differing totals for
   the same vendor (multiple invoices from one vendor naturally differ).
   It now specifically checks whether a vendor's invoiced totals exceed
   what their contract authorizes — the actual audit-relevant check.
"""

from agents.state import PipelineState

MISMATCH_TOLERANCE = 1  # currency units; accounts for rounding


def cross_check_node(state: PipelineState) -> PipelineState:
    """LangGraph node: populates state['flags'] from state['extracted']."""
    state["status"] = "checking"
    flags = []

    for record in state["extracted"]:
        filename = record["filename"]
        doc_type = record.get("document_type", "unknown")
        amounts = record.get("amounts") or {}
        subtotal = amounts.get("subtotal")
        tax = amounts.get("tax") or 0
        total = amounts.get("total")

        # Internal consistency: subtotal + tax should equal total
        if subtotal is not None and total is not None:
            if abs((subtotal + tax) - total) > MISMATCH_TOLERANCE:
                flags.append({
                    "filename": filename,
                    "issue": f"Subtotal + tax ({subtotal + tax:.2f}) does not match total ({total:.2f})",
                    "severity": "high",
                })

        # Missing identifier check — field checked depends on document type,
        # since a contract legitimately has no invoice number and vice versa.
        if doc_type == "invoice" and not record.get("invoice_number"):
            flags.append({
                "filename": filename, "issue": "Missing invoice number", "severity": "medium",
            })
        elif doc_type == "contract" and not record.get("contract_number"):
            flags.append({
                "filename": filename, "issue": "Missing contract number", "severity": "medium",
            })

        if total is None:
            flags.append({
                "filename": filename, "issue": "Missing total amount", "severity": "high",
            })

    # Cross-document check: does a vendor's invoiced total exceed what their
    # contract actually authorizes? This is the audit-relevant comparison —
    # simply noting that two invoices from the same vendor have different
    # totals is expected and not worth flagging on its own.
    by_vendor: dict[str, list] = {}
    for record in state["extracted"]:
        vendor = record.get("vendor_name")
        if vendor:
            by_vendor.setdefault(vendor, []).append(record)

    for vendor, records in by_vendor.items():
        contracts = [r for r in records if r.get("document_type") == "contract"]
        invoices = [r for r in records if r.get("document_type") == "invoice"]

        if not contracts or not invoices:
            continue  # nothing to reconcile against

        for contract in contracts:
            contract_value = (contract.get("amounts") or {}).get("total")
            if contract_value is None:
                continue

            for invoice in invoices:
                invoice_total = (invoice.get("amounts") or {}).get("total")
                if invoice_total is None:
                    continue

                if invoice_total > contract_value:
                    flags.append({
                        "filename": f"{invoice['filename']} vs {contract['filename']}",
                        "issue": (
                            f"Invoice total ({invoice_total:,.2f}) for vendor '{vendor}' "
                            f"exceeds contract value ({contract_value:,.2f})"
                        ),
                        "severity": "medium",
                    })

    state["flags"] = flags
    return state
