from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routers import jobs as jobs_router


def test_root_redirects_to_jobs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/jobs"


def test_ocr_route_returns_extracted_text(client, monkeypatch):
    monkeypatch.setattr(jobs_router, "extract_text_from_image", lambda content: "추출된 공고 텍스트")
    response = client.post("/jobs/ocr", files={"file": ("shot.png", b"imgbytes", "image/png")})
    assert response.status_code == 200
    assert response.json() == {"text": "추출된 공고 텍스트"}


def test_ocr_route_rejects_oversized_upload(client):
    big = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post("/jobs/ocr", files={"file": ("shot.png", big, "image/png")})
    assert response.status_code == 400
    assert "너무 큽니다" in response.json()["detail"]


def test_ocr_route_maps_runtime_error_to_400(client, monkeypatch):
    def _boom(content):
        raise RuntimeError("Tesseract-OCR 가 설치돼 있지 않습니다")

    monkeypatch.setattr(jobs_router, "extract_text_from_image", _boom)
    response = client.post("/jobs/ocr", files={"file": ("shot.png", b"img", "image/png")})
    assert response.status_code == 400
    assert "Tesseract" in response.json()["detail"]


def test_job_and_resume_form_pages_render(client, job_factory, resume_factory):
    future = (date.today() + timedelta(days=30)).isoformat()
    job = job_factory(employment_type="contract", remote_policy="hybrid", deadline=future)
    resume = resume_factory()
    for url in ("/jobs/new", f"/jobs/{job.id}/edit", "/resumes/new", f"/resumes/{resume.id}/edit"):
        assert client.get(url).status_code == 200
    detail = client.get(f"/jobs/{job.id}").text
    assert "계약직" in detail and "하이브리드" in detail and f"마감 {future}" in detail


@pytest.fixture()
def error_routes():
    """Register throwaway routes that raise, then remove them, so the
    exception handlers in app/main.py can be exercised."""
    async def _unhandled():
        raise RuntimeError("의도적 예외")

    async def _server_http():
        raise HTTPException(status_code=503, detail="점검 중")

    app.add_api_route("/_test/unhandled", _unhandled, methods=["GET"])
    app.add_api_route("/_test/server-http", _server_http, methods=["GET"])
    try:
        yield
    finally:
        app.router.routes = [
            r for r in app.router.routes
            if getattr(r, "path", "") not in ("/_test/unhandled", "/_test/server-http")
        ]


def test_lifespan_runs_init_db(monkeypatch):
    calls = []
    monkeypatch.setattr("app.main.init_db", lambda: calls.append(True))
    with TestClient(app):
        pass
    assert calls == [True]


def test_unhandled_exception_renders_500_page_for_browsers(error_routes, lenient_client):
    response = lenient_client.get("/_test/unhandled", headers={"accept": "text/html"})
    assert response.status_code == 500
    assert "text/html" in response.headers["content-type"]


def test_unhandled_exception_is_plain_500_for_non_browsers(error_routes, lenient_client):
    response = lenient_client.get("/_test/unhandled", headers={"accept": "application/json"})
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


def test_server_http_exception_renders_500_page_for_browsers(error_routes, client):
    response = client.get("/_test/server-http", headers={"accept": "text/html"})
    assert response.status_code == 503
    assert "text/html" in response.headers["content-type"]


def test_job_list_flags_imminent_deadline(client, job_factory):
    soon = (date.today() + timedelta(days=3)).isoformat()
    later = (date.today() + timedelta(days=60)).isoformat()
    job_factory(title="임박 공고", deadline=soon)
    job_factory(title="여유 공고", deadline=later)
    listing = client.get("/jobs").text
    assert "마감 D-3" in listing
    assert f"마감 {later}" in listing
