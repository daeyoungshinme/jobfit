import io
import os
import shutil

import pytesseract
from PIL import Image, UnidentifiedImageError

_WINDOWS_DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_configured = False


def _ensure_tesseract_configured() -> None:
    """Point pytesseract at a working tesseract binary, or fail clearly.

    Tesseract isn't pip-installable — it's a separate Windows program the
    user installs themselves, and its installer doesn't always add it to
    PATH. This tries PATH first (the common case once installed with the
    PATH option checked), then falls back to the UB-Mannheim installer's
    default location before giving up with a Korean message that tells the
    user what to do, since "TesseractNotFoundError" alone is not actionable.
    """
    global _configured
    if _configured:
        return
    if shutil.which("tesseract") is None and os.path.exists(_WINDOWS_DEFAULT_TESSERACT):
        pytesseract.pytesseract.tesseract_cmd = _WINDOWS_DEFAULT_TESSERACT
    _configured = True


def extract_text_from_image(content: bytes) -> str:
    """Extract text from a screenshot/photo of a job posting via OCR.

    Raises RuntimeError with a Korean, user-facing message on failure
    (missing Tesseract install, missing Korean language pack, or a file
    that isn't a readable image) so the router can surface it as-is.
    """
    _ensure_tesseract_configured()
    try:
        image = Image.open(io.BytesIO(content))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise RuntimeError("이미지 파일을 읽을 수 없습니다. 스크린샷/사진 파일인지 확인해주세요.")

    try:
        return pytesseract.image_to_string(image, lang="kor+eng")
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract-OCR이 설치되어 있지 않습니다. "
            "https://github.com/UB-Mannheim/tesseract/wiki 에서 설치 후 다시 시도해주세요."
        )
    except pytesseract.TesseractError as exc:
        message = str(exc)
        if "kor" in message.lower():
            raise RuntimeError(
                "한국어 언어팩(kor.traineddata)이 설치되어 있지 않습니다. "
                "Tesseract 설치 시 Korean을 추가로 선택해주세요."
            )
        raise RuntimeError(f"이미지에서 텍스트를 추출하지 못했습니다: {message}")
