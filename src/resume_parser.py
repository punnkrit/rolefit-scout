from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from docx import Document
from pypdf import PdfReader


class ResumeParseError(ValueError):
    pass


def parse_resume_file(file_obj: BinaryIO, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    data = file_obj.read()
    if suffix == ".pdf":
        return parse_pdf(data)
    if suffix == ".docx":
        return parse_docx(data)
    if suffix in {".txt", ""}:
        return parse_txt(data)
    raise ResumeParseError("Unsupported file type. Upload PDF, DOCX, or TXT.")


def parse_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pragma: no cover - library-specific failures
        raise ResumeParseError("Could not parse the PDF resume.") from exc
    return _clean_resume_text(text)


def parse_docx(data: bytes) -> str:
    try:
        document = Document(BytesIO(data))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:  # pragma: no cover - library-specific failures
        raise ResumeParseError("Could not parse the DOCX resume.") from exc
    return _clean_resume_text(text)


def parse_txt(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return _clean_resume_text(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise ResumeParseError("Could not decode the text resume.")


def _clean_resume_text(text: str) -> str:
    cleaned = "\n".join(line.strip() for line in (text or "").splitlines() if line.strip())
    if not cleaned:
        raise ResumeParseError("Resume text is empty after parsing.")
    return cleaned
