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
