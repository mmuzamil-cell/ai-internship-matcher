"""
utils/pdf_parser.py — PDF text extraction helper.

Wraps PyPDF2 so route handlers don't need to know about PDF internals.
Returns clean, stripped text ready for skill extraction.
"""

import io
import logging
from typing import Optional

import PyPDF2

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> Optional[str]:
    """
    Extract all plain text from a PDF given its raw bytes.

    Why bytes instead of a file path?
    The file arrives as an in-memory UploadFile from FastAPI. We extract
    text before saving to disk so we can validate content early and avoid
    storing empty or unreadable files.

    Args:
        file_bytes: Raw bytes of the PDF file (from await file.read()).

    Returns:
        A single string of all page text joined by newlines, or None if the
        PDF could not be read (e.g., encrypted, corrupted, or image-only).
    """
    try:
        # Wrap bytes in a file-like object — PyPDF2 expects a seekable stream
        pdf_stream = io.BytesIO(file_bytes)
        reader = PyPDF2.PdfReader(pdf_stream)

        # Bail early on encrypted PDFs we cannot decrypt
        if reader.is_encrypted:
            logger.warning("Uploaded PDF is password-protected; cannot extract text.")
            return None

        pages_text: list[str] = []
        for page_num, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text.strip())
            except Exception as page_err:
                # Skip unreadable pages (e.g., scanned image pages) but continue
                logger.debug("Could not extract text from page %d: %s", page_num, page_err)

        if not pages_text:
            logger.info("PDF had no extractable text — may be a scanned/image PDF.")
            return None

        # Join all pages with double newline for readability
        full_text = "\n\n".join(pages_text)
        return full_text

    except PyPDF2.errors.PdfReadError as e:
        logger.error("PyPDF2 failed to read PDF: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error extracting PDF text: %s", e)
        return None


def count_pages(file_bytes: bytes) -> int:
    """
    Return the number of pages in a PDF (useful for validation/logging).
    Returns 0 if the PDF cannot be read.
    """
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return len(reader.pages)
    except Exception:
        return 0
