"""
chunker.py
Splits raw document text into overlapping chunks suitable for embedding.
Uses a simple character-based sliding window with overlap — good enough
for a portfolio project; swap for a token-aware splitter later if needed.
"""

CHUNK_SIZE = 1000      # characters per chunk
CHUNK_OVERLAP = 150    # overlap between consecutive chunks, preserves context across boundaries


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Splits text into overlapping chunks. Overlap matters here specifically
    because financial figures (e.g., a total) can sit right at a chunk
    boundary — without overlap you risk splitting a number from its label.
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


if __name__ == "__main__":
    sample = "A" * 2500
    result = chunk_text(sample)
    print(f"{len(result)} chunks produced from {len(sample)} chars")
    for i, c in enumerate(result):
        print(f"Chunk {i}: {len(c)} chars")
