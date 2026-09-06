"""
hybrid_retriever.py
Combines BM25 keyword search with ChromaDB vector search using Reciprocal
Rank Fusion (RRF). This fixes cases like "penalty clause for late payment"
where pure vector search under-ranks a small number of exact-keyword-match
chunks against a much larger pool of semantically-similar-but-wrong chunks.

BM25 index is rebuilt in memory each run by pulling all chunks out of
ChromaDB — fine at this project's scale (a few thousand chunks); a
production system would persist the BM25 index separately instead.
"""

import os
import re
import chromadb
import ollama
from rank_bm25 import BM25Okapi

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_store")
COLLECTION_NAME = "financial_docs"
EMBED_MODEL = "nomic-embed-text"

RRF_K = 60  # standard smoothing constant for reciprocal rank fusion


def embed(text: str, is_query: bool = False) -> list[float]:
    prefix = "search_query: " if is_query else "search_document: "
    return ollama.embeddings(model=EMBED_MODEL, prompt=prefix + text)["embedding"]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class HybridRetriever:
    """
    Load once per process (e.g., once when your FastAPI app starts, or once
    per pipeline run) — rebuilding the BM25 index on every single query
    would be wasteful.
    """

    def __init__(self, source_filter: str | None = None):
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.client.get_collection(COLLECTION_NAME)

        where = {"source": source_filter} if source_filter else None
        all_data = self.collection.get(where=where, include=["documents", "metadatas"])

        self.ids = all_data["ids"]
        self.documents = all_data["documents"]
        self.metadatas = all_data["metadatas"]
        self.source_filter = source_filter

        tokenized_corpus = [_tokenize(doc) for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def _bm25_ranked_ids(self, query: str) -> list[str]:
        scores = self.bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.ids, scores), key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in ranked]

    def _vector_ranked_ids(self, query: str, n_results: int) -> list[str]:
        where = {"source": self.source_filter} if self.source_filter else None
        results = self.collection.query(
            query_embeddings=[embed(query, is_query=True)],
            n_results=min(n_results, len(self.ids)),
            where=where,
        )
        return results["ids"][0]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Returns top_k chunks as dicts: {id, text, source, chunk_index, score}
        Ranked by Reciprocal Rank Fusion across BM25 and vector search.
        """
        bm25_ranked = self._bm25_ranked_ids(query)
        # Pull a generous pool from vector search too, so fusion has enough to work with
        vector_pool_size = max(top_k * 4, 20)
        vector_ranked = self._vector_ranked_ids(query, vector_pool_size)

        rrf_scores: dict[str, float] = {}
        for rank, doc_id in enumerate(bm25_ranked[: max(top_k * 4, 20)]):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (RRF_K + rank + 1)
        for rank, doc_id in enumerate(vector_ranked):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (RRF_K + rank + 1)

        fused_ranked_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        id_to_index = {doc_id: i for i, doc_id in enumerate(self.ids)}
        output = []
        for doc_id, score in fused_ranked_ids:
            idx = id_to_index[doc_id]
            output.append({
                "id": doc_id,
                "text": self.documents[idx],
                "source": self.metadatas[idx]["source"],
                "chunk_index": self.metadatas[idx]["chunk_index"],
                "score": score,
            })
        return output


if __name__ == "__main__":
    retriever = HybridRetriever()
    query = "penalty clause for late payment"
    results = retriever.search(query, top_k=5)

    print(f"Hybrid search results for: {query!r}\n")
    for rank, r in enumerate(results, start=1):
        preview = r["text"][:120].replace("\n", " ")
        print(f"{rank}. [{r['source']} | chunk {r['chunk_index']} | RRF score {r['score']:.4f}] {preview}...")
