import io

import pytest
from docx import Document

from app.services.resume_parser import extract_text_from_upload

# Minimal hand-crafted PDF with no proper xref table — pdfminer's recovery
# mode can still parse this, so it's enough to exercise the real
# pdfplumber.open()/extract_text() path without pulling in a PDF-writing
# dependency just for tests.
_MINIMAL_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 200 200] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT /F1 24 Tf 10 100 Td (Hello) Tj ET
endstream
endobj
trailer
<< /Size 6 /Root 1 0 R >>
%%EOF
"""


def _build_docx_bytes(paragraph_text: str) -> bytes:
    document = Document()
    document.add_paragraph(paragraph_text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def test_extract_pdf_text():
    text = extract_text_from_upload("resume.pdf", _MINIMAL_PDF)
    assert "Hello" in text


def test_extract_docx_text():
    text = extract_text_from_upload("resume.docx", _build_docx_bytes("파이썬 백엔드 개발 3년"))
    assert "파이썬 백엔드 개발 3년" in text


def test_extract_txt_utf8():
    text = extract_text_from_upload("resume.txt", "경력: 백엔드 개발 3년".encode("utf-8"))
    assert text == "경력: 백엔드 개발 3년"


def test_extract_txt_falls_back_to_cp949():
    # Legacy Korean-Windows editors (e.g. old Notepad) commonly save .txt as
    # CP949/EUC-KR rather than UTF-8 — decoding as UTF-8-only used to
    # silently mangle this into replacement characters.
    text = extract_text_from_upload("resume.txt", "경력: 백엔드 개발 3년".encode("cp949"))
    assert text == "경력: 백엔드 개발 3년"


def test_extract_unsupported_extension_raises():
    with pytest.raises(ValueError):
        extract_text_from_upload("resume.hwp", b"whatever")


def test_extract_corrupt_pdf_raises_value_error():
    with pytest.raises(ValueError):
        extract_text_from_upload("resume.pdf", b"not a real pdf")


def test_extract_corrupt_docx_raises_value_error():
    with pytest.raises(ValueError):
        extract_text_from_upload("resume.docx", b"not a real docx")
