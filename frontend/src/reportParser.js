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
  let benford = null;

  const lines = markdown.split("\n");
  let section = null;
  let benfordLines = [];

  for (const line of lines) {
    const countMatch = line.match(/Documents processed:\s*(\d+)/);
    if (countMatch) docCount = countMatch[1];

    if (line.startsWith("## Summary")) { section = "summary"; continue; }
    if (line.startsWith("## Flagged Issues")) { section = "findings"; continue; }
    if (line.startsWith("## Statistical Analysis")) { section = "benford"; continue; }

    if (section === "summary") {
      const m = line.match(/-\s+\*\*(.+?)\*\*\s+—\s+Vendor:\s*(.+?),\s*Total:\s*(.+)/);
      if (m) {
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

    if (section === "benford") {
      benfordLines.push(line);
    }
  }

  if (benfordLines.length > 0) {
    const text = benfordLines.join("\n");
    const insufficientMatch = text.match(/Sample size \((\d+) documents.*?minimum \((\d+)\)/s);
    const analyzedMatch = text.match(/Sample size:\s*(\d+).*?Chi-square statistic:\s*([\d.]+),\s*p-value:\s*(\d+\.\d+)/s);
    const conforms = text.includes("conforms to Benford's Law");

    if (insufficientMatch) {
      benford = { status: "insufficient_data", sampleSize: insufficientMatch[1], minimumRequired: insufficientMatch[2] };
    } else if (analyzedMatch) {
      const digitRows = [];
      const rowRegex = /\|\s*(\d)\s*\|\s*([\d.]+)%\s*\|\s*([\d.]+)%\s*\|/g;
      let rm;
      while ((rm = rowRegex.exec(text)) !== null) {
        digitRows.push({ digit: rm[1], observed: rm[2], expected: rm[3] });
      }
      benford = {
        status: "analyzed",
        sampleSize: analyzedMatch[1],
        chiSquare: analyzedMatch[2],
        pValue: analyzedMatch[3],
        conforms,
        digitRows,
      };
    }
  }

  const highCount = findings.filter((f) => f.severity === "HIGH").length;
  const mediumCount = findings.filter((f) => f.severity === "MEDIUM").length;
  const totalReviewed = summaryRows
    .filter((r) => !r.isFiling)
    .reduce((sum, r) => sum + r.total, 0);

  return { docCount, summaryRows, findings, highCount, mediumCount, totalReviewed, benford };
}
