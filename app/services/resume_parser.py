import io

import pdfplumber
from docx import Document


def extract_text_from_upload(filename: str, content: bytes) -> str:
    """Extract plain text from an uploaded résumé file (PDF, DOCX, or TXT)."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(content)
    if lower.endswith(".docx"):
        return _extract_docx(content)
    if lower.endswith(".txt"):
        return _decode_text(content)
    raise ValueError(f"지원하지 않는 파일 형식입니다: {filename}")


def _decode_text(content: bytes) -> str:
    """Decode a .txt upload, falling back from UTF-8 to CP949.

    Plain UTF-8-only decoding silently mangles the EUC-KR/CP949 text files
    that older Korean-Windows editors (e.g. legacy Notepad) still produce.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return content.decode("cp949")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="replace")


def _extract_pdf(content: bytes) -> str:
    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as exc:
        raise ValueError("PDF 파일을 읽을 수 없습니다. 파일이 손상되었거나 암호로 보호되어 있을 수 있습니다.") from exc
    return "\n".join(text_parts)


def _extract_docx(content: bytes) -> str:
    try:
        document = Document(io.BytesIO(content))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text)
    except Exception as exc:
        raise ValueError("DOCX 파일을 읽을 수 없습니다. 파일이 손상되었거나 지원하지 않는 형식일 수 있습니다.") from exc
    return "\n".join(paragraphs)
