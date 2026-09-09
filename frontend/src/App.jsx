import { useState, useRef, useCallback } from "react";

const API_BASE = "http://localhost:8000";

const STAGES = [
  { key: "indexing", label: "Indexing" },
  { key: "running", label: "Analyzing" },
  { key: "done", label: "Complete" },
];

/**
 * Parses the pipeline's markdown report into structured data (a summary
 * table + a findings register) rather than rendering markdown line-by-line.
 * This is intentionally coupled to reporting_agent.py's exact output
 * format — see agents/reporting_agent.py.
 */
function parseReport(markdown) {
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
      if (m) summaryRows.push({ filename: m[1], vendor: m[2], total: parseFloat(m[3]) || 0 });
    }

    if (section === "findings") {
      const m = line.match(/-\s+\[(HIGH|MEDIUM|LOW)\]\s+(.+?):\s+(.+)/);
      if (m) findings.push({ severity: m[1], filename: m[2], issue: m[3] });
    }
  }

  const highCount = findings.filter((f) => f.severity === "HIGH").length;
  const mediumCount = findings.filter((f) => f.severity === "MEDIUM").length;
  const totalReviewed = summaryRows.reduce((sum, r) => sum + r.total, 0);

  return { docCount, summaryRows, findings, highCount, mediumCount, totalReviewed };
}

function formatCurrency(n) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}


function Stepper({ status }) {
  const currentIndex = STAGES.findIndex((s) => s.key === status);
  return (
    <div className="flex items-center gap-0">
      {STAGES.map((stage, i) => {
        const isDone = currentIndex > i || status === "done";
        const isActive = currentIndex === i && status !== "done";
        return (
          <div key={stage.key} className="flex items-center">
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  isDone || isActive ? "bg-brand" : "bg-rule"
                } ${isActive ? "animate-pulse" : ""}`}
              />
              <span
                className={`text-sm font-mono ${
                  isDone || isActive ? "text-ink" : "text-ink-muted"
                }`}
              >
                {stage.label}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <div className={`w-8 h-px mx-3 ${currentIndex > i ? "bg-brand" : "bg-rule"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function SeverityMark({ severity }) {
  const styles = {
    HIGH: "text-high",
    MEDIUM: "text-medium",
    LOW: "text-ink-muted",
  };
  return (
    <span className={`font-mono text-xs font-semibold tracking-wide ${styles[severity] || styles.LOW}`}>
      {severity}
    </span>
  );
}

function HeroMetrics({ docCount, totalReviewed, highCount, mediumCount }) {
  return (
    <div className="grid grid-cols-3 divide-x divide-rule border border-rule bg-white mb-6">
      <div className="px-6 py-5">
        <div className="font-mono text-3xl text-ink">{docCount}</div>
        <div className="text-xs text-ink-muted mt-1">documents reviewed</div>
      </div>
      <div className="px-6 py-5">
        <div className="font-mono text-3xl text-ink">₹{formatCurrency(totalReviewed)}</div>
        <div className="text-xs text-ink-muted mt-1">total value reviewed</div>
      </div>
      <div className="px-6 py-5">
        <div className="font-mono text-3xl">
          <span className={highCount > 0 ? "text-high" : "text-clean"}>{highCount}</span>
          <span className="text-rule mx-1">/</span>
          <span className={mediumCount > 0 ? "text-medium" : "text-clean"}>{mediumCount}</span>
        </div>
        <div className="text-xs text-ink-muted mt-1">high / medium findings</div>
      </div>
    </div>
  );
}

function ReportDocument({ report, jobId }) {
  const { docCount, summaryRows, findings, highCount, mediumCount, totalReviewed } = parseReport(report);

  return (
    <>
      <HeroMetrics docCount={docCount} totalReviewed={totalReviewed} highCount={highCount} mediumCount={mediumCount} />

      <div className="border border-rule border-t-4 border-t-brand bg-white">
        <div className="px-8 py-6 border-b border-rule">
          <h2 className="font-serif text-2xl text-ink">Findings report</h2>
          <div className="mt-2 flex items-center gap-4 text-sm text-ink-muted font-mono">
            <span>engagement {jobId}</span>
          </div>
        </div>

        <div className="px-8 py-6 border-b border-rule">
          <h3 className="text-sm font-medium text-ink-muted mb-4">Document summary</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-muted border-b border-rule">
                <th className="font-normal pb-2 pr-4">Document</th>
                <th className="font-normal pb-2 pr-4">Vendor</th>
                <th className="font-normal pb-2 text-right">Total</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {summaryRows.map((row, i) => (
                <tr key={i} className="border-b border-rule last:border-0 hover:bg-paper/60">
                  <td className="py-2.5 pr-4 text-ink">{row.filename}</td>
                  <td className="py-2.5 pr-4 text-ink-muted">{row.vendor}</td>
                  <td className="py-2.5 text-right text-ink tabular-nums">₹{formatCurrency(row.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="px-8 py-6">
          <h3 className="text-sm font-medium text-ink-muted mb-4">Findings</h3>
          {findings.length === 0 ? (
            <p className="text-sm text-clean font-mono">No issues found.</p>
          ) : (
            <div className="-mx-8">
              {findings.map((f, i) => {
                const bg = f.severity === "HIGH" ? "bg-high-bg" : f.severity === "MEDIUM" ? "bg-medium-bg" : "";
                const border = f.severity === "HIGH" ? "border-high" : f.severity === "MEDIUM" ? "border-medium" : "border-ink-muted";
                return (
                  <div key={i} className={`px-8 py-4 border-l-4 ${border} ${bg} ${i > 0 ? "border-t border-t-rule" : ""}`}>
                    <div className="flex items-center gap-3">
                      <SeverityMark severity={f.severity} />
                      <span className="font-mono text-sm text-ink">{f.filename}</span>
                    </div>
                    <p className="text-sm text-ink-muted mt-1 ml-0">{f.issue}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export default function App() {
  const [files, setFiles] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  const addFiles = (fileList) => {
    const pdfs = Array.from(fileList).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    setFiles((prev) => [...prev, ...pdfs]);
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  }, []);

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const resetForNewRun = () => {
    setJobId(null);
    setStatus(null);
    setReport(null);
    setErrorMsg(null);
    if (pollRef.current) clearInterval(pollRef.current);
  };

  const pollStatus = (id) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${id}`);
        const data = await res.json();
        setStatus(data.status);

        if (data.status === "done") {
          clearInterval(pollRef.current);
          const reportRes = await fetch(`${API_BASE}/report/${id}`);
          const reportData = await reportRes.json();
          setReport(reportData.report);
        } else if (data.status === "error") {
          clearInterval(pollRef.current);
          setErrorMsg("Processing failed. Check the backend logs for details.");
        }
      } catch (err) {
        clearInterval(pollRef.current);
        setErrorMsg("Lost connection to the backend while checking status.");
      }
    }, 3000);
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    resetForNewRun();

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    try {
      const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json();
        setErrorMsg(err.detail || "Upload failed.");
        return;
      }
      const data = await res.json();
      setJobId(data.job_id);
      setStatus(data.status);
      pollStatus(data.job_id);
    } catch (err) {
      setErrorMsg("Could not reach the backend. Is it running on localhost:8000?");
    }
  };

  const isProcessing = status && status !== "done" && status !== "error";

  return (
    <div className="min-h-screen bg-paper">
      <div className="max-w-3xl mx-auto px-6 py-14">
        <header className="mb-12 pb-8 border-b-2 border-brand">
          <h1 className="font-serif text-5xl text-ink tracking-tight">Ledger</h1>
          <p className="mt-3 text-ink-muted text-sm max-w-md">
            Upload invoices, contracts, and filings. Ledger extracts the figures
            and flags what doesn't reconcile.
          </p>
        </header>

        {!jobId && (
          <section className="mb-10">
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border border-dashed cursor-pointer transition-colors px-8 py-12 text-center
                ${isDragging ? "border-brand bg-brand/5" : "border-rule hover:border-ink-muted"}`}
            >
              <p className="text-ink font-medium">Drop PDF documents here</p>
              <p className="text-ink-muted text-sm mt-1">or click to browse</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                multiple
                onChange={(e) => addFiles(e.target.files)}
                className="hidden"
              />
            </div>

            {files.length > 0 && (
              <div className="mt-4 border border-rule bg-white">
                <table className="w-full text-sm">
                  <tbody>
                    {files.map((f, i) => (
                      <tr key={i} className="border-b border-rule last:border-0">
                        <td className="py-2.5 px-4 font-mono text-ink">{f.name}</td>
                        <td className="py-2.5 px-4 text-ink-muted text-right font-mono">
                          {(f.size / 1024).toFixed(0)} KB
                        </td>
                        <td className="py-2.5 px-4 text-right w-10">
                          <button
                            onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                            className="text-ink-muted hover:text-high"
                            aria-label={`Remove ${f.name}`}
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={files.length === 0}
              className="mt-5 bg-brand text-paper px-5 py-2.5 text-sm font-medium
                         hover:bg-brand-dark disabled:bg-rule disabled:text-ink-muted
                         disabled:cursor-not-allowed transition-colors"
            >
              Review documents
            </button>
          </section>
        )}

        {errorMsg && (
          <div className="mb-8 border-l-2 border-high bg-high-bg px-4 py-3 text-sm text-high">
            {errorMsg}
          </div>
        )}

        {jobId && (
          <section className="mb-8">
            <Stepper status={status} />
          </section>
        )}

        {report && <ReportDocument report={report} jobId={jobId} />}

        {jobId && (
          <button
            onClick={() => { resetForNewRun(); setFiles([]); }}
            className="mt-6 text-sm text-ink-muted hover:text-ink underline underline-offset-2"
          >
            Start a new review
          </button>
        )}
      </div>
    </div>
  );
}
