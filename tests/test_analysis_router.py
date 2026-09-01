from app.models import JobPosting, Resume


def test_dashboard_skill_ranking_lists_skills_across_jobs(client, db_session):
    job = JobPosting(
        title="백엔드 개발자 채용",
        position="백엔드 개발자",
        raw_text="자격요건\nPython 3년 이상",
        required_skills=["Python"],
        preferred_skills=["Docker"],
    )
    db_session.add(job)
    db_session.commit()

    response = client.get("/analysis/dashboard")
    assert response.status_code == 200
    assert "많이 요구되는 스킬" in response.text
    assert "Python" in response.text


def test_dashboard_skill_ranking_respects_position_filter(client, db_session):
    job = JobPosting(
        title="백엔드 개발자 채용",
        position="백엔드 개발자",
        raw_text="자격요건\nPython 3년 이상",
        required_skills=["Python"],
    )
    db_session.add(job)
    db_session.commit()

    response = client.get("/analysis/dashboard", params={"position": "프론트엔드 개발자"})
    assert response.status_code == 200
    assert "Python" not in response.text


def test_skills_route_is_gone(client):
    assert client.get("/analysis/skills").status_code == 404


def test_dashboard_with_no_data(client):
    response = client.get("/analysis/dashboard")
    assert response.status_code == 200


def test_dashboard_computes_matches_for_selected_resume(client, db_session):
    job = JobPosting(
        title="백엔드 개발자 채용",
        position="백엔드 개발자",
        raw_text="자격요건\nPython 3년 이상",
        required_skills=["Python"],
        preferred_skills=["Docker"],
    )
    resume = Resume(
        label="테스트 이력서",
        source_type="form",
        raw_text="Python 백엔드 개발 3년",
        extracted_skills=["Python"],
    )
    db_session.add_all([job, resume])
    db_session.commit()
    db_session.refresh(resume)

    response = client.get("/analysis/dashboard", params={"resume_id": resume.id})
    assert response.status_code == 200
    assert "백엔드 개발자 채용" in response.text
    # status column renders the job's application status
    assert "관심" in response.text


def test_dashboard_with_unknown_resume_id_shows_no_matches(client):
    response = client.get("/analysis/dashboard", params={"resume_id": 99999})
    assert response.status_code == 200


def test_coach_without_resume_id_redirects_to_resume_not_found(client):
    response = client.get("/analysis/coach", params={"job_id": 1}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_not_found"


def test_coach_without_job_id_redirects_to_job_not_found(client, db_session):
    resume = Resume(label="테스트 이력서", source_type="form", raw_text="Python", extracted_skills=["Python"])
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)

    response = client.get("/analysis/coach", params={"resume_id": resume.id}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_coach_shows_category_grouped_missing_skills(client, db_session):
    job = JobPosting(
        title="백엔드 개발자 채용",
        position="백엔드 개발자",
        raw_text="자격요건\nPython, AWS 3년 이상",
        required_skills=["Python", "AWS"],
        preferred_skills=["Kubernetes"],
    )
    resume = Resume(
        label="테스트 이력서",
        source_type="form",
        raw_text="Python 백엔드 개발 3년",
        extracted_skills=["Python"],
    )
    db_session.add_all([job, resume])
    db_session.commit()
    db_session.refresh(job)
    db_session.refresh(resume)

    response = client.get("/analysis/coach", params={"resume_id": resume.id, "job_id": job.id})
    assert response.status_code == 200
    assert "클라우드/인프라" in response.text
    assert "AWS" in response.text
