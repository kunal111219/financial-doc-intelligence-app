"""
diagnose_10k_extraction.py
Runs retrieval + the extraction prompt against one 10-K and prints the
RAW model output before any JSON parsing — so we can see exactly what
the model actually returned instead of just seeing the fallback dict
that json.JSONDecodeError produces.

Usage (from backend/):
    python diagnose_10k_extraction.py apple_10k_fy2025.pdf
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "retrieval"))

import ollama
from hybrid_retriever import HybridRetriever
from agents.extraction_agent import EXTRACTION_PROMPT

QUERY_TEMPLATES = [
    "invoice number, date, and total amount",
    "vendor or party names and contract terms",
    "payment obligations, due dates, and penalties",
    "total revenue",
    "net income",
    "total assets",
    "total liabilities",
    "total stockholders equity",
]


def main():
    filename = sys.argv[1] if len(sys.argv) > 1 else "apple_10k_fy2025.pdf"

    retriever = HybridRetriever(source_filter=filename)
    print(f"{filename} has {len(retriever.ids)} total chunks indexed.\n")

    matches = {}
    for query in QUERY_TEMPLATES:
        for result in retriever.search(query, top_k=2):
            matches[result["id"]] = (result["chunk_index"], result["text"])

    ordered = sorted(matches.values(), key=lambda pair: pair[0])
    context_text = "\n".join(text for _, text in ordered)[:8000]

    print(f"Retrieved {len(ordered)} unique chunks, {len(context_text)} chars of context.\n")
    print("--- First 500 chars of context sent to the model ---")
    print(context_text[:500])
    print("...\n")

    prompt = EXTRACTION_PROMPT.format(context=context_text)
    print(f"Full prompt length: {len(prompt)} chars\n")

    response = ollama.generate(
        model="mistral",
        prompt=prompt,
        options={"temperature": 0, "top_k": 1, "top_p": 0, "seed": 42},
    )

    print("--- RAW MODEL OUTPUT ---")
    print(response["response"])
    print("--- END RAW MODEL OUTPUT ---")


if __name__ == "__main__":
    main()
