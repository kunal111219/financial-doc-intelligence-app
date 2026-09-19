import { describe, it, expect } from "vitest";
import { parseReport, formatCurrency } from "./reportParser";

const INVOICE_REPORT = `# Financial Document Intelligence Report — Job abc123

Documents processed: 2

## Summary

- **invoice_01_clean_acme.pdf** — Vendor: Acme Supplies Pvt Ltd, Total: 100,300.00
- **invoice_03_error_acme.pdf** — Vendor: Acme Supplies Pvt Ltd, Total: 100,000.00

## Flagged Issues

- [HIGH] invoice_03_error_acme.pdf: Subtotal + tax (106200.00) does not match total (100000.00)
- [MEDIUM] invoice_04_missing_number.pdf: Missing invoice number
`;

const FILING_REPORT = `# Financial Document Intelligence Report — Job def456

Documents processed: 1

## Summary

- **apple_10k_fy2025.pdf** — Vendor: Apple Inc., Total: 359,241.00 (Total Assets)

## Flagged Issues

No issues flagged.
`;

const MIXED_REPORT = `# Financial Document Intelligence Report — Job ghi789

Documents processed: 2

## Summary

- **invoice_01_clean_acme.pdf** — Vendor: Acme Supplies Pvt Ltd, Total: 100,300.00
- **apple_10k_fy2025.pdf** — Vendor: Apple Inc., Total: 359,241.00 (Total Assets)

## Flagged Issues

No issues flagged.
`;

describe("parseReport", () => {
  it("parses comma-formatted invoice totals without truncating at the comma", () => {
    // Regression test: parseFloat("100,300.00") truncates to 100 unless
    // commas are stripped first — this broke every invoice total in the UI
    // after the backend started comma-formatting totals.
    const result = parseReport(INVOICE_REPORT);
    expect(result.summaryRows[0].total).toBe(100300);
    expect(result.summaryRows[1].total).toBe(100000);
  });

  it("extracts document count correctly", () => {
    const result = parseReport(INVOICE_REPORT);
    expect(result.docCount).toBe("2");
  });

  it("parses HIGH and MEDIUM findings with correct severity and filename", () => {
    const result = parseReport(INVOICE_REPORT);
    expect(result.findings).toHaveLength(2);
    expect(result.findings[0].severity).toBe("HIGH");
    expect(result.findings[0].filename).toBe("invoice_03_error_acme.pdf");
    expect(result.findings[1].severity).toBe("MEDIUM");
  });

  it("counts high and medium findings correctly", () => {
    const result = parseReport(INVOICE_REPORT);
    expect(result.highCount).toBe(1);
    expect(result.mediumCount).toBe(1);
  });

  it("sums invoice totals correctly for totalReviewed", () => {
    const result = parseReport(INVOICE_REPORT);
    expect(result.totalReviewed).toBe(200300);
  });

  it("detects a financial_filing row via the '(Total Assets)' suffix", () => {
    const result = parseReport(FILING_REPORT);
    expect(result.summaryRows[0].isFiling).toBe(true);
    expect(result.summaryRows[0].total).toBe(359241);
  });

  it("excludes financial_filing rows from totalReviewed", () => {
    // Regression test: summing an invoice total (thousands) together with
    // a filing's total assets (billions) produces a meaningless blended
    // figure — filings must be excluded from this sum.
    const result = parseReport(MIXED_REPORT);
    expect(result.totalReviewed).toBe(100300); // only the invoice, not + 359241
  });

  it("returns 'No issues flagged' as zero findings, not a false match", () => {
    const result = parseReport(FILING_REPORT);
    expect(result.findings).toHaveLength(0);
  });
});

describe("formatCurrency", () => {
  it("formats with thousands separators and two decimal places", () => {
    expect(formatCurrency(100300)).toBe("100,300.00");
  });

  it("handles zero correctly", () => {
    expect(formatCurrency(0)).toBe("0.00");
  });
});

const BENFORD_ANALYZED_REPORT = `# Report

Documents processed: 80

## Summary

- **invoice_01.pdf** — Vendor: Acme, Total: 100,300.00

## Flagged Issues

No issues flagged.


## Statistical Analysis: Benford's Law

Sample size: 80 documents. Chi-square statistic: 6.31, p-value: 0.6121.

The leading-digit distribution **conforms to Benford's Law** at the p < 0.05 threshold. No further action indicated.

| Leading digit | Observed | Expected (Benford) |
|---|---|---|
| 1 | 41.2% | 30.1% |
| 2 | 12.5% | 17.6% |
`;

const BENFORD_INSUFFICIENT_REPORT = `# Report

Documents processed: 5

## Summary

- **invoice_01.pdf** — Vendor: Acme, Total: 100.00

## Flagged Issues

No issues flagged.


## Statistical Analysis: Benford's Law

Sample size (5 documents with a valid total) is below the minimum (30) needed for a statistically meaningful Benford's Law analysis. No result is reported.
`;

describe("parseReport — Benford's Law section", () => {
  // Regression test: the Benford's Law section was computed correctly by
  // the backend for every report, but the frontend never parsed or
  // rendered it at all — a whole feature was silently invisible in the UI
  // until caught by manual end-to-end testing.

  it("parses an analyzed result with correct sample size, chi-square, and p-value", () => {
    const result = parseReport(BENFORD_ANALYZED_REPORT);
    expect(result.benford.status).toBe("analyzed");
    expect(result.benford.sampleSize).toBe("80");
    expect(result.benford.chiSquare).toBe("6.31");
    expect(result.benford.pValue).toBe("0.6121");
    expect(result.benford.conforms).toBe(true);
  });

  it("does not include a trailing period in the parsed p-value", () => {
    // Regression test: an earlier regex greedily captured the sentence's
    // trailing period, producing "0.6121." instead of "0.6121".
    const result = parseReport(BENFORD_ANALYZED_REPORT);
    expect(result.benford.pValue).not.toMatch(/\.$/);
  });

  it("parses the digit distribution table rows", () => {
    const result = parseReport(BENFORD_ANALYZED_REPORT);
    expect(result.benford.digitRows).toHaveLength(2);
    expect(result.benford.digitRows[0]).toEqual({ digit: "1", observed: "41.2", expected: "30.1" });
  });

  it("detects the insufficient-data case and does not fabricate a statistic", () => {
    const result = parseReport(BENFORD_INSUFFICIENT_REPORT);
    expect(result.benford.status).toBe("insufficient_data");
    expect(result.benford.sampleSize).toBe("5");
    expect(result.benford.minimumRequired).toBe("30");
    expect(result.benford.chiSquare).toBeUndefined();
  });
});
