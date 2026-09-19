"""
test_cross_check_agent.py
Automated regression tests for the audit/cross-check logic — turns the
manual validation done throughout the project (planted-issue documents,
checked by eye against run_pipeline.py output) into a permanent test
suite. Each test's expected outcome matches a real scenario already
validated by hand earlier in the project.

Run from backend/:
    pytest tests/test_cross_check_agent.py -v
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from agents.cross_check_agent import cross_check_node


def make_state(extracted):
    """Minimal pipeline state — cross_check_node only reads state['extracted']."""
    return {
        "job_id": "test",
        "collection_name": "test",
        "documents": [],
        "retrieved_context": {},
        "extracted": extracted,
        "flags": [],
        "report": None,
        "status": "queued",
    }


def flag_issues(state):
    return [f["issue"] for f in state["flags"]]


def has_issue_containing(state, substring):
    return any(substring in issue for issue in flag_issues(state))


# --- Invoice/contract math checks ---

def test_subtotal_tax_mismatch_flagged_high():
    extracted = [{
        "filename": "bad_invoice.pdf", "document_type": "invoice",
        "vendor_name": "Acme", "invoice_number": "INV-1",
        "amounts": {"subtotal": 100000, "tax": 6200, "total": 100000},
        "dates": {}, "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "does not match total")
    assert result["flags"][0]["severity"] == "high"


def test_clean_invoice_produces_no_math_flag():
    extracted = [{
        "filename": "clean_invoice.pdf", "document_type": "invoice",
        "vendor_name": "Acme", "invoice_number": "INV-1",
        "amounts": {"subtotal": 85000, "tax": 15300, "total": 100300},
        "dates": {}, "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert not has_issue_containing(result, "does not match total")


# --- Missing identifier checks, scoped correctly by document type ---

def test_missing_invoice_number_flagged_on_invoice():
    extracted = [{
        "filename": "no_number.pdf", "document_type": "invoice",
        "vendor_name": "Acme", "invoice_number": None,
        "amounts": {"subtotal": 100, "tax": 0, "total": 100},
        "dates": {}, "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "Missing invoice number")


def test_contract_not_flagged_for_missing_invoice_number():
    """Regression test: contracts were previously flagged for a field that
    doesn't apply to them at all — a real bug found in Phase 3."""
    extracted = [{
        "filename": "contract.pdf", "document_type": "contract",
        "vendor_name": "Acme", "invoice_number": None, "contract_number": "CON-1",
        "amounts": {"subtotal": None, "tax": None, "total": 500000},
        "dates": {}, "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert not has_issue_containing(result, "Missing invoice number")


def test_missing_contract_number_flagged_on_contract():
    extracted = [{
        "filename": "contract.pdf", "document_type": "contract",
        "vendor_name": "Acme", "contract_number": None,
        "amounts": {"subtotal": None, "tax": None, "total": 500000},
        "dates": {}, "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "Missing contract number")


# --- Round-number / structuring check, scoped to invoices only ---

def test_round_number_invoice_flagged_low():
    extracted = [{
        "filename": "round_invoice.pdf", "document_type": "invoice",
        "vendor_name": "Acme", "invoice_number": "INV-1",
        "amounts": {"subtotal": 100000, "tax": 0, "total": 100000},
        "dates": {}, "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "suspiciously round number")


def test_round_number_contract_not_flagged():
    """Regression test: negotiated contract values are legitimately round
    (e.g. 500,000) — flagging them produced false positives in testing."""
    extracted = [{
        "filename": "contract.pdf", "document_type": "contract",
        "vendor_name": "Acme", "contract_number": "CON-1",
        "amounts": {"subtotal": None, "tax": None, "total": 500000},
        "dates": {}, "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert not has_issue_containing(result, "suspiciously round number")


# --- Date logic ---

def test_due_date_before_invoice_date_flagged():
    extracted = [{
        "filename": "baddate.pdf", "document_type": "invoice",
        "vendor_name": "BlueWave", "invoice_number": "INV-1",
        "amounts": {"subtotal": 100, "tax": 0, "total": 100},
        "dates": {"invoice_date": "2026-07-15", "due_date": "2026-07-01"},
        "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "is before invoice date")


def test_normal_date_order_not_flagged():
    extracted = [{
        "filename": "gooddate.pdf", "document_type": "invoice",
        "vendor_name": "BlueWave", "invoice_number": "INV-1",
        "amounts": {"subtotal": 100, "tax": 0, "total": 100},
        "dates": {"invoice_date": "2026-07-01", "due_date": "2026-07-15"},
        "financials": {},
    }]
    result = cross_check_node(make_state(extracted))
    assert not has_issue_containing(result, "is before invoice date")


# --- Duplicate invoice detection ---

def test_duplicate_invoice_flagged():
    extracted = [
        {
            "filename": "inv_a.pdf", "document_type": "invoice",
            "vendor_name": "Acme", "invoice_number": "INV-1",
            "amounts": {"subtotal": 100300, "tax": 0, "total": 100300},
            "dates": {"invoice_date": "2026-06-01"}, "financials": {},
        },
        {
            "filename": "inv_b.pdf", "document_type": "invoice",
            "vendor_name": "Acme", "invoice_number": "INV-2",
            "amounts": {"subtotal": 100300, "tax": 0, "total": 100300},
            "dates": {"invoice_date": "2026-06-03"}, "financials": {},
        },
    ]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "Possible duplicate invoice")


def test_same_vendor_different_totals_not_flagged_as_duplicate():
    extracted = [
        {
            "filename": "inv_a.pdf", "document_type": "invoice",
            "vendor_name": "Acme", "invoice_number": "INV-1",
            "amounts": {"subtotal": 100000, "tax": 0, "total": 100000},
            "dates": {"invoice_date": "2026-06-01"}, "financials": {},
        },
        {
            "filename": "inv_b.pdf", "document_type": "invoice",
            "vendor_name": "Acme", "invoice_number": "INV-2",
            "amounts": {"subtotal": 50000, "tax": 0, "total": 50000},
            "dates": {"invoice_date": "2026-06-02"}, "financials": {},
        },
    ]
    result = cross_check_node(make_state(extracted))
    assert not has_issue_containing(result, "duplicate")


# --- Sequence gap detection, with the tuned threshold ---

def test_large_sequence_gap_flagged():
    extracted = [
        {
            "filename": "inv_a.pdf", "document_type": "invoice",
            "vendor_name": "Greenfield", "invoice_number": "INV-3004",
            "amounts": {"subtotal": 100, "tax": 0, "total": 100},
            "dates": {}, "financials": {},
        },
        {
            "filename": "inv_b.pdf", "document_type": "invoice",
            "vendor_name": "Greenfield", "invoice_number": "INV-3011",
            "amounts": {"subtotal": 100, "tax": 0, "total": 100},
            "dates": {}, "financials": {},
        },
    ]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "Gap in invoice number sequence")


def test_small_sequence_gap_not_flagged():
    """Regression test: gaps below SEQUENCE_GAP_THRESHOLD (routine — voided
    invoices, shared number pools) should not fire. Raised from >1 to >5
    after 58 false positives at scale in testing."""
    extracted = [
        {
            "filename": "inv_a.pdf", "document_type": "invoice",
            "vendor_name": "Greenfield", "invoice_number": "INV-3004",
            "amounts": {"subtotal": 100, "tax": 0, "total": 100},
            "dates": {}, "financials": {},
        },
        {
            "filename": "inv_b.pdf", "document_type": "invoice",
            "vendor_name": "Greenfield", "invoice_number": "INV-3007",
            "amounts": {"subtotal": 100, "tax": 0, "total": 100},
            "dates": {}, "financials": {},
        },
    ]
    result = cross_check_node(make_state(extracted))
    assert not has_issue_containing(result, "Gap in invoice number sequence")


# --- Vendor invoice-vs-contract check ---

def test_invoice_exceeding_contract_value_flagged():
    extracted = [
        {
            "filename": "contract.pdf", "document_type": "contract",
            "vendor_name": "Acme", "contract_number": "CON-1",
            "amounts": {"subtotal": None, "tax": None, "total": 500000},
            "dates": {}, "financials": {},
        },
        {
            "filename": "invoice.pdf", "document_type": "invoice",
            "vendor_name": "Acme", "invoice_number": "INV-1",
            "amounts": {"subtotal": 767000, "tax": 0, "total": 767000},
            "dates": {}, "financials": {},
        },
    ]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "exceeds contract value")


def test_invoice_within_contract_value_not_flagged():
    extracted = [
        {
            "filename": "contract.pdf", "document_type": "contract",
            "vendor_name": "Acme", "contract_number": "CON-1",
            "amounts": {"subtotal": None, "tax": None, "total": 500000},
            "dates": {}, "financials": {},
        },
        {
            "filename": "invoice.pdf", "document_type": "invoice",
            "vendor_name": "Acme", "invoice_number": "INV-1",
            "amounts": {"subtotal": 100300, "tax": 0, "total": 100300},
            "dates": {}, "financials": {},
        },
    ]
    result = cross_check_node(make_state(extracted))
    assert not has_issue_containing(result, "exceeds contract value")


# --- Financial filing: accounting identity check ---

def test_filing_identity_holds_not_flagged():
    """Uses Apple's real, independently-verified figures — the identity
    holds exactly, so no flag should fire."""
    extracted = [{
        "filename": "apple_10k.pdf", "document_type": "financial_filing",
        "vendor_name": None, "amounts": {}, "dates": {},
        "financials": {
            "company_name": "Apple Inc.", "total_revenue": 391000,
            "net_income": 93700, "total_assets": 359241,
            "total_liabilities": 285508, "stockholders_equity": 73733,
        },
    }]
    result = cross_check_node(make_state(extracted))
    assert not has_issue_containing(result, "Accounting identity does not hold")


def test_filing_identity_mismatch_flagged():
    extracted = [{
        "filename": "bad_filing.pdf", "document_type": "financial_filing",
        "vendor_name": None, "amounts": {}, "dates": {},
        "financials": {
            "company_name": "Test Corp", "total_revenue": 1000,
            "net_income": 100, "total_assets": 284668,
            "total_liabilities": 185050, "stockholders_equity": 28306,
        },
    }]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "Accounting identity does not hold")


def test_filing_missing_fields_flagged_medium():
    extracted = [{
        "filename": "incomplete_filing.pdf", "document_type": "financial_filing",
        "vendor_name": None, "amounts": {}, "dates": {},
        "financials": {
            "company_name": "Test Corp", "total_assets": 100000,
            "total_liabilities": None, "stockholders_equity": None,
        },
    }]
    result = cross_check_node(make_state(extracted))
    assert has_issue_containing(result, "Could not verify accounting identity")
    matching = [f for f in result["flags"] if "Could not verify" in f["issue"]]
    assert matching[0]["severity"] == "medium"
