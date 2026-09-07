from datetime import date, timedelta

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


def test_job_list_flags_imminent_deadline(client, job_factory):
    soon = (date.today() + timedelta(days=3)).isoformat()
    later = (date.today() + timedelta(days=60)).isoformat()
    job_factory(title="임박 공고", deadline=soon)
    job_factory(title="여유 공고", deadline=later)
    listing = client.get("/jobs").text
    assert "마감 D-3" in listing
    assert f"마감 {later}" in listing
