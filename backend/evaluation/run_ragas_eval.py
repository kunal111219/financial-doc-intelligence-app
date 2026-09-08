"""
run_ragas_eval.py
Phase 4 entry point. For each labeled question:
  1. Retrieve context using the same HybridRetriever used in production
  2. Generate an answer via Ollama (mistral), grounded in that context
  3. Score the result with RAGAS metrics, using local Ollama models as the
     judge/embedding backend (no paid API required)

Metrics used:
  - context_precision / context_recall — is retrieval finding the right stuff?
  - faithfulness — is the generated answer actually supported by the context?
  - answer_relevancy — does the answer actually address the question?

Usage (from backend/):
    python evaluation/run_ragas_eval.py
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "retrieval"))
sys.path.append(os.path.dirname(__file__))

import ollama
from hybrid_retriever import HybridRetriever
from eval_dataset import EVAL_QUESTIONS

from ragas import evaluate, EvaluationDataset
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig
from langchain_ollama import ChatOllama, OllamaEmbeddings

ANSWER_PROMPT = """Answer the question using ONLY the context below. If the context doesn't
contain the answer, say "I don't know" — do not guess.

Context:
---
{context}
---

Question: {question}

Answer:"""


def generate_answer(question: str, contexts: list[str]) -> str:
    context_text = "\n\n".join(contexts)
    response = ollama.generate(
        model="mistral",
        prompt=ANSWER_PROMPT.format(context=context_text, question=question),
        options={"temperature": 0, "top_k": 1, "top_p": 0, "seed": 42},
    )
    return response["response"].strip()


def build_eval_samples() -> list[dict]:
    """Runs retrieval + generation for every labeled question."""
    retriever = HybridRetriever()  # searches across the whole indexed corpus
    samples = []

    for item in EVAL_QUESTIONS:
        question = item["question"]
        print(f"Processing: {question!r}")

        # top_k=10 rather than 5 — diagnosed via diagnose_msft_fy_query.py that
        # a correct, exact-match chunk (a 10-K's cover-page fiscal year date)
        # ranked 9th, just outside a top_5 cutoff, because it's out-scored by
        # denser financial-table chunks that repeat the same terms many times.
        # A single, sparse-but-correct mention loses to term-frequency-heavy
        # chunks under both BM25 and embedding similarity at shallow depth.
        results = retriever.search(question, top_k=10)
        contexts = [r["text"] for r in results]

        answer = generate_answer(question, contexts)

        samples.append({
            "user_input": question,
            "response": answer,
            "retrieved_contexts": contexts,
            "reference": item["ground_truth"],
        })

    return samples


def main():
    samples = build_eval_samples()
    dataset = EvaluationDataset.from_list(samples)

    # Local, free judge — no OpenAI key needed
    judge_llm = LangchainLLMWrapper(ChatOllama(model="mistral", temperature=0))
    judge_embeddings = LangchainEmbeddingsWrapper(OllamaEmbeddings(model="nomic-embed-text"))

    # Local Ollama processes requests serially on CPU — RAGAS defaults to
    # high concurrency built for fast paid APIs, which causes most calls to
    # time out waiting in queue. Lowering concurrency and raising the
    # per-call timeout lets local inference actually keep up.
    run_config = RunConfig(timeout=300, max_workers=2)

    results = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(),
            AnswerRelevancy(),
            ContextPrecision(),
            ContextRecall(),
        ],
        llm=judge_llm,
        embeddings=judge_embeddings,
        run_config=run_config,
    )

    print("\n" + "=" * 60)
    print("RAGAS Evaluation Results")
    print("=" * 60)
    df = results.to_pandas()
    print(df[["user_input", "faithfulness", "answer_relevancy", "context_precision", "context_recall"]])

    print("\nAverages:")
    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        print(f"  {metric}: {df[metric].mean():.3f}")

    df.to_csv(os.path.join(os.path.dirname(__file__), "ragas_results.csv"), index=False)
    print(f"\nFull results saved to evaluation/ragas_results.csv")


if __name__ == "__main__":
    main()
