"""
loader.py
Loads every PDF in data/raw/, extracting text natively via pdfplumber,
with an OCR fallback (pytesseract) for scanned pages that come back empty.
Long documents (like 200-300 page 10-Ks) are handled page-by-page so
memory stays reasonable.
"""

import os
import pdfplumber

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
MIN_CHARS_PER_PAGE = 40  # below this, a page is likely a scanned image


def extract_text_native(pdf_path: str) -> str:
    text_chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if len(page_text.strip()) < MIN_CHARS_PER_PAGE:
                page_text = _ocr_page_fallback(page)
            text_chunks.append(page_text)
    return "\n".join(text_chunks)


def _ocr_page_fallback(page) -> str:
    """OCR a single page image if native extraction returned near-nothing."""
    try:
        import pytesseract
        image = page.to_image(resolution=300).original
        return pytesseract.image_to_string(image)
    except Exception:
        return ""  # OCR unavailable or failed — skip rather than crash the whole batch


def load_all_documents() -> dict[str, str]:
    """
    Returns {filename: raw_text} for every PDF in data/raw/.
    Skips files that fail to open, printing a warning rather than crashing
    the batch (useful since 10-Ks and synthetic docs vary a lot in structure).
    """
    documents = {}
    if not os.path.isdir(RAW_DIR):
        raise FileNotFoundError(f"Expected raw documents at {RAW_DIR}")

    for filename in sorted(os.listdir(RAW_DIR)):
        if not filename.lower().endswith(".pdf"):
            continue
        full_path = os.path.join(RAW_DIR, filename)
        try:
            print(f"Loading {filename}...")
            documents[filename] = extract_text_native(full_path)
        except Exception as e:
            print(f"  ! Failed to load {filename}: {e}")

    return documents


if __name__ == "__main__":
    docs = load_all_documents()
    for name, text in docs.items():
        print(f"{name}: {len(text)} characters extracted")
