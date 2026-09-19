/**
 * reportParser.js
 * Parses the pipeline's markdown report into structured data (a summary
 * table + a findings register). Extracted out of App.jsx so this logic —
 * which has already had one real regression (comma-truncation, see
 * formatCurrency/parseReport history) — can be unit tested directly rather
 * than only exercised through full component rendering.
 */

export function formatCurrency(n) {
  // Locale explicitly pinned to "en-US" rather than left as `undefined` —
  // `undefined` uses the runtime's system locale, which produces different
  // digit grouping on different machines (e.g. Indian numbering — lakh/crore
  // grouping like "1,00,300.00" — vs. Western "100,300.00"). A financial
  // report's number formatting should be consistent regardless of the
  // viewer's OS locale, not silently vary by machine.
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function parseReport(markdown) {
  const summaryRows = [];
  const findings = [];
  let docCount = null;

  const lines = markdown.split("\n");
  let section = null;

  for (const line of lines) {
    const countMatch = line.match(/Documents processed:\s*(\d+)/);
    if (countMatch) docCount = countMatch[1];

    if (line.startsWith("## Summary")) { section = "summary"; continue; }
    if (line.startsWith("## Flagged Issues")) { section = "findings"; continue; }

    if (section === "summary") {
      const m = line.match(/-\s+\*\*(.+?)\*\*\s+—\s+Vendor:\s*(.+?),\s*Total:\s*(.+)/);
      if (m) {
        // Backend formats totals with thousands separators (e.g. "100,300.00")
        // and appends "(Total Assets)" for financial_filing rows — strip
        // commas before parseFloat (which otherwise truncates at the first
        // comma, e.g. "100,300.00" -> 100 — a real regression found after
        // the backend started comma-formatting totals) and detect the
        // filing suffix so its total isn't summed together with invoice
        // totals, which would produce a meaningless blended figure.
        const rawTotal = m[3];
        const isFiling = rawTotal.includes("(Total Assets)");
        const numericTotal = parseFloat(rawTotal.replace(/,/g, "")) || 0;
        summaryRows.push({ filename: m[1], vendor: m[2], total: numericTotal, isFiling });
      }
    }

    if (section === "findings") {
      const m = line.match(/-\s+\[(HIGH|MEDIUM|LOW)\]\s+(.+?):\s+(.+)/);
      if (m) findings.push({ severity: m[1], filename: m[2], issue: m[3] });
    }
  }

  const highCount = findings.filter((f) => f.severity === "HIGH").length;
  const mediumCount = findings.filter((f) => f.severity === "MEDIUM").length;
  const totalReviewed = summaryRows
    .filter((r) => !r.isFiling)
    .reduce((sum, r) => sum + r.total, 0);

  return { docCount, summaryRows, findings, highCount, mediumCount, totalReviewed };
}
