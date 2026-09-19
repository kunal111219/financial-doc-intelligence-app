"""
benford_analysis.py
A batch-level (not per-document) statistical check: does the leading-digit
distribution of extracted invoice totals conform to Benford's Law?

This is fundamentally different from every other check in this project —
it says nothing about any single document, only about the population of
totals as a whole. Real auditors use deviation from Benford's Law as a
soft signal worth investigating further, not proof of fraud on its own.

Gated on sample size deliberately: Benford's Law is a statistical
distribution that only becomes meaningful with a reasonably large sample.
Running it on a handful of documents and reporting a result would be
statistically meaningless — worse than not running it at all, since a
chart or verdict implies a real finding the data can't support. The
threshold below (30) is a commonly cited practical floor in forensic
accounting literature for a first-pass test; serious use in practice
often wants hundreds of data points for a confident conclusion.
"""

from collections import Counter
import math

from scipy import stats

MIN_SAMPLE_SIZE = 30

# Benford's Law: P(leading digit = d) = log10(1 + 1/d)
EXPECTED_PROPORTIONS = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def _leading_digit(amount: float) -> int | None:
    if amount is None or amount <= 0:
        return None
    s = f"{amount:.10f}".lstrip("0").lstrip(".")
    for ch in s:
        if ch.isdigit() and ch != "0":
            return int(ch)
    return None


def analyze_totals(amounts: list[float]) -> dict:
    """
    Returns a dict describing the result. Always check result["status"]
    first — "insufficient_data" means no statistical claim is made at all.
    """
    digits = [d for d in (_leading_digit(a) for a in amounts) if d is not None]
    n = len(digits)

    if n < MIN_SAMPLE_SIZE:
        return {
            "status": "insufficient_data",
            "sample_size": n,
            "minimum_required": MIN_SAMPLE_SIZE,
        }

    observed_counts = Counter(digits)
    observed = [observed_counts.get(d, 0) for d in range(1, 10)]
    expected = [EXPECTED_PROPORTIONS[d] * n for d in range(1, 10)]

    chi2_stat, p_value = stats.chisquare(f_obs=observed, f_exp=expected)

    # Conventional interpretation: p < 0.05 suggests the observed distribution
    # is unlikely to have arisen if the data genuinely followed Benford's Law —
    # worth a closer look, not proof of anything.
    conforms = p_value >= 0.05

    return {
        "status": "analyzed",
        "sample_size": n,
        "chi_square_statistic": chi2_stat,
        "p_value": p_value,
        "conforms_to_benford": conforms,
        "observed_distribution": {d: observed_counts.get(d, 0) / n for d in range(1, 10)},
        "expected_distribution": EXPECTED_PROPORTIONS,
    }


def format_benford_section(result: dict) -> str:
    """Formats the analysis result as a markdown section for the report."""
    lines = ["## Statistical Analysis: Benford's Law\n"]

    if result["status"] == "insufficient_data":
        lines.append(
            f"Sample size ({result['sample_size']} documents with a valid total) is below "
            f"the minimum ({result['minimum_required']}) needed for a statistically meaningful "
            f"Benford's Law analysis. No result is reported — a conclusion from too small a "
            f"sample would not be reliable."
        )
        return "\n".join(lines)

    verdict = "conforms to" if result["conforms_to_benford"] else "deviates from"
    lines.append(
        f"Sample size: {result['sample_size']} documents. "
        f"Chi-square statistic: {result['chi_square_statistic']:.2f}, "
        f"p-value: {result['p_value']:.4f}."
    )
    lines.append(
        f"\nThe leading-digit distribution **{verdict} Benford's Law** at the p < 0.05 threshold. "
        f"{'No further action indicated.' if result['conforms_to_benford'] else 'This is a soft signal worth investigating further — not proof of any specific issue.'}"
    )

    lines.append("\n| Leading digit | Observed | Expected (Benford) |")
    lines.append("|---|---|---|")
    for d in range(1, 10):
        obs_pct = result["observed_distribution"][d] * 100
        exp_pct = result["expected_distribution"][d] * 100
        lines.append(f"| {d} | {obs_pct:.1f}% | {exp_pct:.1f}% |")

    return "\n".join(lines)
