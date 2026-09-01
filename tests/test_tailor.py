from app.models import JobPosting, Resume


def _make_job(db_session):
    job = JobPosting(
        title="백엔드 개발자 채용",
        company="테스트회사",
        position="백엔드 개발자",
        raw_text="[자격요건]\nPython, Kafka 경험",
        required_text="Python, Kafka 경험",
        required_skills=["Python", "Kafka"],
        preferred_skills=[],
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _make_form_resume(db_session):
    resume = Resume(
        label="테스트 이력서",
        source_type="form",
        raw_text="[경력]\nPython 백엔드 3년\n\n[프로젝트]\n\n[학력]\n\n[기술 스택]\nPython",
        structured={"career": "Python 백엔드 3년", "projects": "", "education": "", "skills_text": "Python"},
        extracted_skills=["Python"],
    )
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)
    return resume


def test_tailor_redirects_without_resume(client):
    response = client.get("/analysis/tailor", params={"job_id": 1}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_not_found"


def test_tailor_redirects_without_job(client, db_session):
    resume = _make_form_resume(db_session)
    response = client.get(
        "/analysis/tailor", params={"resume_id": resume.id}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_tailor_get_shows_job_requirements_and_resume_fields(client, db_session):
    job = _make_job(db_session)
    resume = _make_form_resume(db_session)

    response = client.get("/analysis/tailor", params={"resume_id": resume.id, "job_id": job.id})
    assert response.status_code == 200
    assert "Kafka" in response.text  # missing required skill chip
    assert "Python 백엔드 3년" in response.text  # existing résumé career field value


def test_tailor_post_reextracts_skills_and_shrinks_gap(client, db_session):
    job = _make_job(db_session)
    resume = _make_form_resume(db_session)

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
    assert "✓ Kafka" in followup.text


def test_tailor_post_file_resume_updates_raw_text_only(client, db_session):
    job = _make_job(db_session)
    resume = Resume(
        label="파일 이력서",
        source_type="file",
        raw_text="원본 텍스트 Python",
        structured={"original_filename": "resume.pdf"},
        extracted_skills=["Python"],
    )
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)

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
