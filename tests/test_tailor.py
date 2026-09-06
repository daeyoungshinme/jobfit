def test_tailor_redirects_without_resume(client):
    response = client.get("/analysis/tailor", params={"job_id": 1}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_not_found"


def test_tailor_redirects_without_job(client, resume_factory):
    resume = resume_factory()
    response = client.get(
        "/analysis/tailor", params={"resume_id": resume.id}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_tailor_get_shows_job_requirements_and_resume_fields(client, job_factory, resume_factory):
    job = job_factory()
    resume = resume_factory()

    response = client.get("/analysis/tailor", params={"resume_id": resume.id, "job_id": job.id})
    assert response.status_code == 200
    assert "Kafka" in response.text  # missing required skill chip
    assert "Python 백엔드 3년" in response.text  # existing résumé career field value


def test_tailor_post_reextracts_skills_and_shrinks_gap(client, db_session, job_factory, resume_factory):
    job = job_factory()
    resume = resume_factory()

    save = client.post(
        "/analysis/tailor",
        params={"resume_id": resume.id, "job_id": job.id},
        data={
            "career": "Python 백엔드 3년, Kafka 스트리밍 파이프라인 구축",
            "projects": "",
            "education": "",
            "skills_text": "Python, Kafka",
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    db_session.refresh(resume)
    assert "Kafka" in resume.extracted_skills

    followup = client.get("/analysis/tailor", params={"resume_id": resume.id, "job_id": job.id})
    assert "+ Kafka" not in followup.text  # no longer offered as a missing-skill chip


def test_tailor_post_file_resume_updates_raw_text_only(client, db_session, job_factory, file_resume_factory):
    job = job_factory()
    resume = file_resume_factory()

    client.post(
        "/analysis/tailor",
        params={"resume_id": resume.id, "job_id": job.id},
        data={"raw_text": "수정된 텍스트 Python Kafka"},
        follow_redirects=False,
    )
    db_session.refresh(resume)
    assert resume.raw_text == "수정된 텍스트 Python Kafka"
    assert resume.structured == {"original_filename": "resume.pdf"}
    assert "Kafka" in resume.extracted_skills


def test_tailor_post_form_resume_rejects_all_blank_fields(client, db_session, job_factory, resume_factory):
    job = job_factory()
    resume = resume_factory()  # form source

    response = client.post(
        "/analysis/tailor",
        params={"resume_id": resume.id, "job_id": job.id},
        data={"career": "", "projects": "", "education": "", "skills_text": "   "},
        follow_redirects=False,
    )
    assert response.status_code == 422

    db_session.refresh(resume)
    assert resume.structured["career"] == "Python 백엔드 3년"
    assert resume.extracted_skills == ["Python"]


def test_tailor_post_file_resume_rejects_blank_raw_text(client, db_session, job_factory, file_resume_factory):
    job = job_factory()
    resume = file_resume_factory()

    response = client.post(
        "/analysis/tailor",
        params={"resume_id": resume.id, "job_id": job.id},
        data={"raw_text": "   "},
        follow_redirects=False,
    )
    assert response.status_code == 422

    db_session.refresh(resume)
    assert resume.raw_text == "원본 텍스트 Python"
    assert resume.extracted_skills == ["Python"]
