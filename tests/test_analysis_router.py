def test_dashboard_skill_ranking_lists_skills_across_jobs(client, job_factory):
    job_factory(required_skills=["Python"], preferred_skills=["Docker"])

    response = client.get("/analysis/dashboard")
    assert response.status_code == 200
    assert "많이 요구되는 스킬" in response.text
    assert "Python" in response.text


def test_dashboard_skill_ranking_respects_position_filter(client, job_factory):
    job_factory(required_skills=["Python"], preferred_skills=[])

    response = client.get("/analysis/dashboard", params={"position": "frontend"})
    assert response.status_code == 200
    # the only job is filtered out, so the skill-ranking section is not rendered
    assert "많이 요구되는 스킬" not in response.text


def test_skills_route_is_gone(client):
    assert client.get("/analysis/skills").status_code == 404


def test_dashboard_with_no_data(client):
    response = client.get("/analysis/dashboard")
    assert response.status_code == 200


def test_dashboard_computes_matches_for_selected_resume(client, job_factory, resume_factory):
    job_factory(required_skills=["Python"], preferred_skills=["Docker"])
    resume = resume_factory(raw_text="Python 백엔드 개발 3년", extracted_skills=["Python"])

    response = client.get("/analysis/dashboard", params={"resume_id": resume.id})
    assert response.status_code == 200
    assert "백엔드 개발자 채용" in response.text
    # match row renders (job title link + the job's application status word)
    assert "관심" in response.text


def test_dashboard_with_unknown_resume_id_shows_no_matches(client):
    response = client.get("/analysis/dashboard", params={"resume_id": 99999})
    assert response.status_code == 200


def test_dashboard_axes_1_folds_experience_into_score(client, job_factory, resume_factory):
    job_factory(required_skills=["Python"], experience_level="y5_10")
    resume = resume_factory(raw_text="Python 백엔드 1년", extracted_skills=["Python"], total_years=1)

    baseline = client.get("/analysis/dashboard", params={"resume_id": resume.id})
    with_axes = client.get("/analysis/dashboard", params={"resume_id": resume.id, "axes": 1})

    assert with_axes.status_code == 200
    assert "경력 적합도를 점수에 반영 중" in with_axes.text
    assert "경력 적합도를 점수에 반영 중" not in baseline.text


def test_activity_page_renders(client, job_factory):
    job_factory(status="applied", applied_via="linkedin", applied_at="2026-08-01")
    job_factory(is_inbound=True, status="interest")
    response = client.get("/analysis/activity")
    assert response.status_code == 200
    assert "구직 활동 대시보드" in response.text
    assert "LinkedIn" in response.text
    assert "무응답" in response.text
    assert 'href="/analysis/activity"' in response.text  # 내비 링크


def test_activity_page_empty(client):
    response = client.get("/analysis/activity")
    assert response.status_code == 200
    assert "기록된 지원 채널이 없습니다" in response.text


def test_profile_page_shows_picker_without_resume(client):
    response = client.get("/analysis/profile")
    assert response.status_code == 200
    assert "이력서를 선택하세요" in response.text


def test_profile_page_renders_platform_cards(client, resume_factory, job_factory):
    resume = resume_factory()
    job_factory()
    response = client.get("/analysis/profile", params={"resume_id": resume.id})
    assert response.status_code == 200
    assert "LinkedIn" in response.text
    assert "리멤버" in response.text
    assert "복사" in response.text


def test_profile_page_unknown_resume_id_ok(client):
    response = client.get("/analysis/profile", params={"resume_id": 99999})
    assert response.status_code == 200


def test_coach_without_resume_id_redirects_to_resume_not_found(client):
    response = client.get("/analysis/coach", params={"job_id": 1}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_not_found"


def test_coach_without_job_id_redirects_to_job_not_found(client, resume_factory):
    resume = resume_factory(raw_text="Python", extracted_skills=["Python"])

    response = client.get("/analysis/coach", params={"resume_id": resume.id}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_interview_without_resume_id_redirects(client):
    response = client.get("/analysis/interview", params={"job_id": 1}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_not_found"


def test_interview_with_unknown_job_id_redirects(client, resume_factory):
    resume = resume_factory()
    response = client.get(
        "/analysis/interview", params={"resume_id": resume.id, "job_id": 99999}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_interview_page_renders_question_groups(client, resume_factory, job_factory):
    resume = resume_factory()
    job = job_factory()
    response = client.get("/analysis/interview", params={"resume_id": resume.id, "job_id": job.id})
    assert response.status_code == 200
    assert "면접 예상 질문" in response.text
    assert "인성·행동" in response.text


def test_interview_page_shows_gap_study_topic(client, resume_factory, job_factory):
    resume = resume_factory(extracted_skills=["Python"])
    job = job_factory(required_skills=["Python", "Kafka"], preferred_skills=[])
    response = client.get("/analysis/interview", params={"resume_id": resume.id, "job_id": job.id})
    assert response.status_code == 200
    assert "Kafka 학습" in response.text


def test_interview_resume_only_mode_renders_notice(client, resume_factory):
    resume = resume_factory()
    response = client.get("/analysis/interview", params={"resume_id": resume.id})
    assert response.status_code == 200
    assert "공고를 선택하지 않아" in response.text


def test_coach_and_dashboard_link_to_interview(client, resume_factory, job_factory):
    resume = resume_factory()
    job = job_factory()

    coach = client.get("/analysis/coach", params={"resume_id": resume.id, "job_id": job.id})
    assert "/analysis/interview?resume_id=" in coach.text

    dashboard = client.get("/analysis/dashboard", params={"resume_id": resume.id})
    assert "/analysis/interview?" in dashboard.text


def test_coach_shows_category_grouped_missing_skills(client, job_factory, resume_factory):
    job = job_factory(required_skills=["Python", "AWS"], preferred_skills=["Kubernetes"])
    resume = resume_factory(raw_text="Python 백엔드 개발 3년", extracted_skills=["Python"])

    response = client.get("/analysis/coach", params={"resume_id": resume.id, "job_id": job.id})
    assert response.status_code == 200
    assert "클라우드/인프라" in response.text
    assert "AWS" in response.text
