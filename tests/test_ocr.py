import io

import pytesseract
import pytest
from PIL import Image

from app.services import ocr


def _sample_image_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buf, format="PNG")
    return buf.getvalue()


def test_extract_text_calls_tesseract_with_korean_and_english(monkeypatch):
    captured = {}

    def fake_image_to_string(image, lang=None):
        captured["lang"] = lang
        return "채용공고 텍스트"

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", fake_image_to_string)

    result = ocr.extract_text_from_image(_sample_image_bytes())

    assert result == "채용공고 텍스트"
    assert captured["lang"] == "kor+eng"


def test_missing_tesseract_binary_raises_korean_message(monkeypatch):
    def raise_not_found(image, lang=None):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", raise_not_found)

    with pytest.raises(RuntimeError, match="Tesseract-OCR"):
        ocr.extract_text_from_image(_sample_image_bytes())


def test_missing_korean_language_pack_raises_korean_message(monkeypatch):
    def raise_lang_error(image, lang=None):
        raise pytesseract.TesseractError(1, "Failed loading language 'kor'")

    monkeypatch.setattr(ocr.pytesseract, "image_to_string", raise_lang_error)

    with pytest.raises(RuntimeError, match="언어팩"):
        ocr.extract_text_from_image(_sample_image_bytes())


def test_non_image_file_raises_clear_error():
    with pytest.raises(RuntimeError, match="이미지 파일을 읽을 수 없습니다"):
        ocr.extract_text_from_image(b"not an image")
