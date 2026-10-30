import logging
from io import BytesIO
from typing import Tuple

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MIME_MAP = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


def get_file_extension(filename: str) -> str:
    """Return the lowercase extension without the dot."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def extract_text(file_bytes: bytes, filename: str) -> Tuple[str, int]:
    """
    Extract plain text from PDF, DOCX, or TXT bytes.
    Returns (text, page_count).
    """
    ext = get_file_extension(filename)

    if ext == "pdf":
        return _extract_pdf(file_bytes)
    elif ext == "docx":
        return _extract_docx(file_bytes), 1
    elif ext == "txt":
        return _extract_txt(file_bytes), 1
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(file_bytes: bytes) -> Tuple[str, int]:
    """Extract text from PDF using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        full_text = "\n\n".join(pages)
        return full_text, len(reader.pages)
    except Exception as e:
        logger.error("PDF extraction error: %s", e)
        raise RuntimeError(f"Could not extract PDF text: {e}") from e


def _extract_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document
        doc = Document(BytesIO(file_bytes))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error("DOCX extraction error: %s", e)
        raise RuntimeError(f"Could not extract DOCX text: {e}") from e


def _extract_txt(file_bytes: bytes) -> str:
    """Decode plain text with UTF-8 fallback to latin-1."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")
