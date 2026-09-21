# Backend image: FastAPI + LangGraph pipeline.
# Does NOT bundle Ollama itself (a 4GB+ model download has no place inside
# an application image) — connects to a separate Ollama service instead,
# configured via the OLLAMA_HOST environment variable (see docker-compose.yml).

FROM python:3.11-slim

WORKDIR /app

# System dependencies for pdf2image/pytesseract's OCR fallback path.
# Not required for the common case (native PDF text extraction), but the
# image should work for the code path that does need it rather than fail
# only when a scanned document is uploaded.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data directories the app writes to at runtime (job uploads, ChromaDB
# persistence) — created here so they exist even before a volume is mounted.
RUN mkdir -p data/raw data/jobs chroma_store

EXPOSE 8000

# OLLAMA_HOST defaults to the docker-compose service name; overridable for
# local (non-compose) runs where Ollama is installed on the host instead.
ENV OLLAMA_HOST=http://ollama:11434

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
