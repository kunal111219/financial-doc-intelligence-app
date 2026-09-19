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
