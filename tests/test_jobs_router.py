from app.models import JobPosting


def test_job_detail_404_when_missing(client):
    response = client.get("/jobs/99999")
    assert response.status_code == 404


def test_job_detail_200_when_exists(client, db_session):
    job = JobPosting(title="백엔드 개발자 채용", position="백엔드 개발자", raw_text="자격요건\n파이썬 3년 이상")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.get(f"/jobs/{job.id}")
    assert response.status_code == 200
    assert "백엔드 개발자 채용" in response.text


def test_create_job_missing_required_fields_returns_422(client):
    response = client.post("/jobs", data={"title": "", "position": "", "raw_text": ""})
    assert response.status_code == 422


def test_create_job_success_redirects_to_detail(client, db_session):
    response = client.post(
        "/jobs",
        data={
            "title": "백엔드 개발자 채용",
            "position": "백엔드 개발자",
            "raw_text": "[자격요건]\nPython, FastAPI 경험",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/jobs/")

    job = db_session.query(JobPosting).one()
    assert job.title == "백엔드 개발자 채용"
    assert "Python" in job.required_skills


def test_list_jobs_returns_200(client, db_session):
    job = JobPosting(title="백엔드 개발자 채용", position="백엔드 개발자", raw_text="자격요건\n파이썬 3년 이상")
    db_session.add(job)
    db_session.commit()

    response = client.get("/jobs")
    assert response.status_code == 200
    assert "백엔드 개발자 채용" in response.text


def test_list_jobs_filters_by_position(client, db_session):
    job = JobPosting(title="백엔드 개발자 채용", position="백엔드 개발자", raw_text="자격요건\n파이썬 3년 이상")
    db_session.add(job)
    db_session.commit()

    response = client.get("/jobs", params={"position": "프론트엔드 개발자"})
    assert response.status_code == 200
    assert "백엔드 개발자 채용" not in response.text


def test_edit_job_form_404_when_missing(client):
    response = client.get("/jobs/99999/edit")
    assert response.status_code == 404


def test_update_job_missing_required_fields_returns_422(client, db_session):
    job = JobPosting(title="백엔드 개발자 채용", position="백엔드 개발자", raw_text="자격요건\n파이썬 3년 이상")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.post(f"/jobs/{job.id}/edit", data={"title": "", "position": "", "raw_text": ""})
    assert response.status_code == 422


def test_update_job_404_when_missing(client):
    response = client.post(
        "/jobs/99999/edit",
        data={"title": "제목", "position": "백엔드 개발자", "raw_text": "내용"},
    )
    assert response.status_code == 404


def test_update_job_success_persists_changes(client, db_session):
    job = JobPosting(title="원래 제목", position="백엔드 개발자", raw_text="자격요건\n파이썬 3년 이상")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.post(
        f"/jobs/{job.id}/edit",
        data={
            "title": "수정된 제목",
            "position": "백엔드 개발자",
            "raw_text": "[자격요건]\nPython, Docker 경험",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db_session.refresh(job)
    assert job.title == "수정된 제목"
    assert "Python" in job.required_skills


def test_delete_job_success_redirects_with_flash(client, db_session):
    job = JobPosting(title="삭제될 공고", position="백엔드 개발자", raw_text="자격요건\n파이썬 3년 이상")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.post(f"/jobs/{job.id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_deleted"
    assert db_session.get(JobPosting, job.id) is None


def test_delete_job_missing_redirects_with_not_found_flash(client):
    response = client.post("/jobs/99999/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_preview_job_returns_parsed_fields(client):
    response = client.post("/jobs/preview", data={"raw_text": "[자격요건]\nPython, FastAPI 경험"})
    assert response.status_code == 200
    body = response.json()
    assert "Python" in body["required_skills"]


def test_guess_source_returns_site_name(client):
    response = client.post("/jobs/guess-source", data={"url": "https://www.wanted.co.kr/wd/1"})
    assert response.status_code == 200
    assert response.json() == {"source_site": "원티드"}
