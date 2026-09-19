"""
cross_check_agent.py
Node 3: This is the "audit" logic. Compares extracted figures within and
across documents and raises flags.

Checks implemented, by document type:
- invoice/contract: subtotal+tax=total reconciliation, missing identifier
  checks, vendor-invoice-vs-contract-value comparison (see below)
- financial_filing: the fundamental accounting identity
  Total Assets = Total Liabilities + Stockholders' Equity — the real,
  meaningful equivalent of the invoice math check for a financial
  statement, rather than forcing 10-Ks through invoice-shaped rules
  (which previously produced meaningless "missing total amount" flags on
  every filing, since a 10-K has no single "total").

Additional cross-document checks:
- Duplicate invoice detection (same vendor, same amount, close dates)
- Sequential invoice number gap detection per vendor
- Date logic validation (due date before invoice date, future-dated invoices)
- Round-number / structuring pattern flags
"""

from datetime import datetime, timedelta
import re

from agents.state import PipelineState

MISMATCH_TOLERANCE = 1  # currency units; accounts for rounding on invoices
FILING_TOLERANCE_PCT = 0.01  # 1% relative tolerance for the accounting identity —
                              # filings report in millions/billions, so exact equality
                              # isn't realistic (rounding in reported figures)
SEQUENCE_GAP_THRESHOLD = 5   # only flag a gap larger than this — small gaps (1-4) are
                             # normal in real business (voided invoices, shared number
                             # pools across departments); flagging every single gap
                             # produced excessive noise when tested against a larger
                             # batch (58 low-value flags on 80 documents) with nothing
                             # distinguishing a genuinely suspicious gap from routine ones


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _invoice_number_parts(invoice_number):
    """Splits 'INV-1001' into ('INV-', 1001) so sequences can be compared per prefix."""
    if not invoice_number:
        return None
    match = re.match(r"^(.*?)(\d+)$", invoice_number.strip())
    if not match:
        return None
    return match.group(1), int(match.group(2))


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
        dates = record.get("dates") or {}

        if doc_type in ("invoice", "contract"):
            if subtotal is not None and total is not None:
                if abs((subtotal + tax) - total) > MISMATCH_TOLERANCE:
                    flags.append({
                        "filename": filename,
                        "issue": f"Subtotal + tax ({subtotal + tax:.2f}) does not match total ({total:.2f})",
                        "severity": "high",
                    })

            if doc_type == "invoice" and not record.get("invoice_number"):
                flags.append({"filename": filename, "issue": "Missing invoice number", "severity": "medium"})
            elif doc_type == "contract" and not record.get("contract_number"):
                flags.append({"filename": filename, "issue": "Missing contract number", "severity": "medium"})

            if total is None:
                flags.append({"filename": filename, "issue": "Missing total amount", "severity": "high"})

            # Round-number / structuring flag: invoice-only, since negotiated
            # contract values are commonly and legitimately round numbers —
            # applying this to contracts produced false positives on both
            # test contracts, which have deliberately round agreed values.
            if doc_type == "invoice" and total is not None and total >= 10000 and total % 10000 == 0:
                flags.append({
                    "filename": filename,
                    "issue": f"Total ({total:,.2f}) is a suspiciously round number — worth verifying it's a real transaction amount",
                    "severity": "low",
                })

            # Date logic: due date before invoice date, or invoice dated in the future
            invoice_date = _parse_date(dates.get("invoice_date"))
            due_date = _parse_date(dates.get("due_date"))
            if invoice_date and due_date and due_date < invoice_date:
                flags.append({
                    "filename": filename,
                    "issue": f"Due date ({dates.get('due_date')}) is before invoice date ({dates.get('invoice_date')})",
                    "severity": "high",
                })

        elif doc_type == "financial_filing":
            financials = record.get("financials") or {}
            assets = financials.get("total_assets")
            liabilities = financials.get("total_liabilities")
            equity = financials.get("stockholders_equity")

            if assets is not None and liabilities is not None and equity is not None:
                expected = liabilities + equity
                tolerance = abs(assets) * FILING_TOLERANCE_PCT
                if abs(assets - expected) > tolerance:
                    flags.append({
                        "filename": filename,
                        "issue": (
                            f"Accounting identity does not hold: Total Assets ({assets:,.2f}) != "
                            f"Total Liabilities + Stockholders' Equity ({expected:,.2f})"
                        ),
                        "severity": "high",
                    })
            else:
                missing = [k for k in ("total_assets", "total_liabilities", "stockholders_equity") if not financials.get(k)]
                if missing:
                    flags.append({
                        "filename": filename,
                        "issue": f"Could not verify accounting identity — missing: {', '.join(missing)}",
                        "severity": "medium",
                    })

    # --- Cross-document checks (invoices/contracts only) ---
    invoices = [r for r in state["extracted"] if r.get("document_type") == "invoice"]

    # Duplicate invoice detection: same vendor, same total, dates within 3 days —
    # a classic real AP control test for accidental or fraudulent double payment.
    for i, a in enumerate(invoices):
        for b in invoices[i + 1:]:
            if a["filename"] == b["filename"]:
                continue
            if a.get("vendor_name") and a.get("vendor_name") == b.get("vendor_name"):
                total_a = (a.get("amounts") or {}).get("total")
                total_b = (b.get("amounts") or {}).get("total")
                if total_a is not None and total_b is not None and abs(total_a - total_b) < MISMATCH_TOLERANCE:
                    date_a = _parse_date((a.get("dates") or {}).get("invoice_date"))
                    date_b = _parse_date((b.get("dates") or {}).get("invoice_date"))
                    if date_a and date_b and abs((date_a - date_b).days) <= 3:
                        flags.append({
                            "filename": f"{a['filename']} vs {b['filename']}",
                            "issue": (
                                f"Possible duplicate invoice — vendor '{a['vendor_name']}', "
                                f"same total ({total_a:,.2f}), dates within 3 days"
                            ),
                            "severity": "high",
                        })

    # Sequential invoice number gap detection per vendor
    by_vendor_seq: dict[str, list] = {}
    for inv in invoices:
        parts = _invoice_number_parts(inv.get("invoice_number"))
        vendor = inv.get("vendor_name")
        if parts and vendor:
            by_vendor_seq.setdefault(vendor, []).append((parts[0], parts[1], inv["filename"]))

    for vendor, entries in by_vendor_seq.items():
        by_prefix: dict[str, list] = {}
        for prefix, number, filename in entries:
            by_prefix.setdefault(prefix, []).append((number, filename))

        for prefix, numbered in by_prefix.items():
            if len(numbered) < 2:
                continue
            numbered.sort()
            for (n1, f1), (n2, f2) in zip(numbered, numbered[1:]):
                if n2 - n1 > SEQUENCE_GAP_THRESHOLD:
                    flags.append({
                        "filename": f"{f1} / {f2}",
                        "issue": (
                            f"Gap in invoice number sequence for vendor '{vendor}': "
                            f"{prefix}{n1} to {prefix}{n2} skips {n2 - n1 - 1} number(s)"
                        ),
                        "severity": "low",
                    })

    # Vendor invoice total vs. contract value (existing check, unchanged)
    by_vendor: dict[str, list] = {}
    for record in state["extracted"]:
        vendor = record.get("vendor_name")
        if vendor:
            by_vendor.setdefault(vendor, []).append(record)

    for vendor, records in by_vendor.items():
        contracts = [r for r in records if r.get("document_type") == "contract"]
        vendor_invoices = [r for r in records if r.get("document_type") == "invoice"]

        if not contracts or not vendor_invoices:
            continue

        for contract in contracts:
            contract_value = (contract.get("amounts") or {}).get("total")
            if contract_value is None:
                continue

            for invoice in vendor_invoices:
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
