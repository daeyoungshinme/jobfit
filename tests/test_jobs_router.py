from datetime import date

from app.models import JobPosting


def test_job_detail_404_when_missing(client):
    response = client.get("/jobs/99999")
    assert response.status_code == 404


def test_job_detail_404_renders_styled_page_for_browsers(client):
    response = client.get("/jobs/99999", headers={"accept": "text/html"})
    assert response.status_code == 404
    assert "페이지를 찾을 수 없습니다" in response.text
    assert "존재하지 않는 채용공고입니다" in response.text


def test_job_detail_200_when_exists(client, job_factory):
    job = job_factory(title="백엔드 개발자 채용", raw_text="자격요건\n파이썬 3년 이상")

    response = client.get(f"/jobs/{job.id}")
    assert response.status_code == 200
    assert "백엔드 개발자 채용" in response.text


def test_job_detail_hint_uses_stored_sections_detected(client, db_session):
    client.post("/jobs", data={"title": "구분된 공고", "position": "backend",
                               "raw_text": "[자격요건]\nPython\n[우대사항]\nAWS"})
    client.post("/jobs", data={"title": "줄글 공고", "position": "backend",
                               "raw_text": "헤더 없이 줄글로만 작성된 공고"})
    ok = db_session.query(JobPosting).filter_by(title="구분된 공고").one()
    bad = db_session.query(JobPosting).filter_by(title="줄글 공고").one()
    assert ok.sections_detected is True
    assert bad.sections_detected is False

    assert "공고 형식을 자동으로 나누지 못해" not in client.get(f"/jobs/{ok.id}").text
    assert "공고 형식을 자동으로 나누지 못해" in client.get(f"/jobs/{bad.id}").text


def test_create_job_missing_required_fields_returns_422(client):
    response = client.post("/jobs", data={"title": "", "position": "", "raw_text": ""})
    assert response.status_code == 422


def test_create_job_success_redirects_to_detail(client, db_session):
    response = client.post(
        "/jobs",
        data={
            "title": "백엔드 개발자 채용",
            "position": "backend",
            "raw_text": "[자격요건]\nPython, FastAPI 경험",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/jobs/")

    job = db_session.query(JobPosting).one()
    assert job.title == "백엔드 개발자 채용"
    assert "Python" in job.required_skills


def test_list_jobs_returns_200(client, job_factory):
    job_factory(title="백엔드 개발자 채용", raw_text="자격요건\n파이썬 3년 이상")

    response = client.get("/jobs")
    assert response.status_code == 200
    assert "백엔드 개발자 채용" in response.text


def test_list_jobs_filters_by_position(client, job_factory):
    job_factory(title="백엔드 개발자 채용", raw_text="자격요건\n파이썬 3년 이상")

    response = client.get("/jobs", params={"position": "frontend"})
    assert response.status_code == 200
    assert "백엔드 개발자 채용" not in response.text


def test_edit_job_form_404_when_missing(client):
    response = client.get("/jobs/99999/edit")
    assert response.status_code == 404


def test_update_job_missing_required_fields_returns_422(client, job_factory):
    job = job_factory(title="백엔드 개발자 채용", raw_text="자격요건\n파이썬 3년 이상")

    response = client.post(f"/jobs/{job.id}/edit", data={"title": "", "position": "", "raw_text": ""})
    assert response.status_code == 422


def test_update_job_404_when_missing(client):
    response = client.post(
        "/jobs/99999/edit",
        data={"title": "제목", "position": "backend", "raw_text": "내용"},
    )
    assert response.status_code == 404


def test_update_job_success_persists_changes(client, db_session, job_factory):
    job = job_factory(title="원래 제목", raw_text="자격요건\n파이썬 3년 이상")

    response = client.post(
        f"/jobs/{job.id}/edit",
        data={
            "title": "수정된 제목",
            "position": "backend",
            "raw_text": "[자격요건]\nPython, Docker 경험",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db_session.refresh(job)
    assert job.title == "수정된 제목"
    assert "Python" in job.required_skills


def test_editing_a_job_bumps_updated_at(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="자격요건\nPython")
    db_session.refresh(job)
    original = job.updated_at

    client.post(
        f"/jobs/{job.id}/edit",
        data={"title": "공고 v2", "position": "backend", "raw_text": "[자격요건]\nPython"},
        follow_redirects=False,
    )
    db_session.refresh(job)
    assert job.updated_at >= original
    assert job.updated_at >= job.created_at


def test_delete_job_success_redirects_with_flash(client, db_session, job_factory):
    job = job_factory(title="삭제될 공고", raw_text="자격요건\n파이썬 3년 이상")

    response = client.post(f"/jobs/{job.id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_deleted"
    assert db_session.get(JobPosting, job.id) is None


def test_delete_job_missing_redirects_with_not_found_flash(client):
    response = client.post("/jobs/99999/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_create_job_defaults_status_to_interest(client, db_session):
    client.post(
        "/jobs",
        data={"title": "공고", "position": "backend", "raw_text": "[자격요건]\nPython"},
        follow_redirects=False,
    )
    job = db_session.query(JobPosting).one()
    assert job.status == "interest"


def test_update_job_changes_status(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="자격요건\nPython", status="interest")

    client.post(
        f"/jobs/{job.id}/edit",
        data={
            "title": "공고",
            "position": "backend",
            "raw_text": "[자격요건]\nPython",
            "status": "interview",
        },
        follow_redirects=False,
    )
    db_session.refresh(job)
    assert job.status == "interview"


def test_create_job_rejects_unknown_status(client, db_session):
    response = client.post(
        "/jobs",
        data={
            "title": "공고",
            "position": "backend",
            "raw_text": "[자격요건]\nPython",
            "status": "이상한값",
        },
    )
    assert response.status_code == 422
    assert db_session.query(JobPosting).count() == 0


def test_update_job_rejects_unknown_status(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="자격요건\nPython", status="interest")

    response = client.post(
        f"/jobs/{job.id}/edit",
        data={
            "title": "공고",
            "position": "backend",
            "raw_text": "[자격요건]\nPython",
            "status": "이상한값",
        },
    )
    assert response.status_code == 422
    db_session.refresh(job)
    assert job.status == "interest"


def test_list_jobs_filters_by_status(client, job_factory):
    job_factory(title="관심 공고", raw_text="x", status="interest")
    job_factory(title="면접 공고", raw_text="x", status="interview")

    response = client.get("/jobs", params={"status": "interview"})
    assert "면접 공고" in response.text
    assert "관심 공고" not in response.text


def test_list_jobs_filters_by_experience_skill_and_region(client, job_factory):
    job_factory(title="주니어 서울", raw_text="x", experience_level="y1_3",
                address="서울특별시 강남구", required_skills=["Python"])
    job_factory(title="시니어 부산", raw_text="x", experience_level="y5_10",
                address="부산광역시 해운대구", required_skills=["Go"])

    by_exp = client.get("/jobs", params={"experience_level": "y1_3"}).text
    assert "주니어 서울" in by_exp and "시니어 부산" not in by_exp

    by_region = client.get("/jobs", params={"region": "부산"}).text
    assert "시니어 부산" in by_region and "주니어 서울" not in by_region

    by_skill = client.get("/jobs", params={"skill": "Python"}).text
    assert "주니어 서울" in by_skill and "시니어 부산" not in by_skill


def test_list_jobs_paginates(client, job_factory):
    for i in range(35):
        job_factory(title=f"공고 {i:02d}", raw_text="x")

    page1 = client.get("/jobs").text
    assert "공고 34" in page1  # 최신순 첫 페이지
    assert "공고 00" not in page1
    assert "다음 →" in page1

    page2 = client.get("/jobs", params={"page": 2}).text
    assert "공고 00" in page2
    assert "이전" in page2

    # 범위를 벗어난 page 는 마지막 페이지로 클램프
    assert client.get("/jobs", params={"page": 999}).status_code == 200


def test_list_jobs_pagination_keeps_filters(client, job_factory):
    for i in range(35):
        job_factory(title=f"백엔드 {i:02d}", raw_text="x", status="interview")
    job_factory(title="프론트 관심", raw_text="x", status="interest")

    page2 = client.get("/jobs", params={"status": "interview", "page": 2}).text
    assert "status=interview" in page2  # 페이저 링크가 필터를 유지
    assert "프론트 관심" not in page2


def test_create_job_saves_and_guesses_extra_fields(client, db_session):
    client.post("/jobs", data={
        "title": "공고", "position": "backend",
        "raw_text": "계약직 채용. 재택 근무. 접수 마감: 2026.05.01\n[자격요건]\nPython\n[복지 및 혜택]\n- 맥북 지원",
        "remote_policy": "hybrid",  # 폼 값이 추측을 이긴다
    }, follow_redirects=False)
    job = db_session.query(JobPosting).one()
    assert job.employment_type == "contract"  # 원문에서 추측
    assert job.remote_policy == "hybrid"       # 폼 값 우선
    assert job.deadline == "2026-05-01"
    assert "맥북 지원" in job.benefits_text


def test_list_jobs_filters_by_employment_and_remote(client, job_factory):
    job_factory(title="계약 원격", raw_text="x", employment_type="contract", remote_policy="remote")
    job_factory(title="정규 출근", raw_text="x", employment_type="fulltime", remote_policy="office")

    by_emp = client.get("/jobs", params={"employment_type": "contract"}).text
    assert "계약 원격" in by_emp and "정규 출근" not in by_emp

    by_remote = client.get("/jobs", params={"remote_policy": "office"}).text
    assert "정규 출근" in by_remote and "계약 원격" not in by_remote


def test_preview_returns_extra_guessed_fields(client):
    r = client.post("/jobs/preview", data={"raw_text": "프리랜서 모집. 완전 재택.\n[자격요건]\nPython"})
    body = r.json()
    assert body["employment_type"] == "freelance"
    assert body["remote_policy"] == "remote"


def test_preview_rejects_oversized_raw_text(client):
    response = client.post("/jobs/preview", data={"raw_text": "가" * 50_001})
    assert response.status_code == 400
    assert "너무 깁니다" in response.json()["detail"]


def test_create_job_rejects_oversized_raw_text(client):
    response = client.post(
        "/jobs",
        data={"title": "공고", "position": "backend", "raw_text": "가" * 50_001},
    )
    assert response.status_code == 422
    assert "너무 깁니다" in response.text


def test_create_job_rejects_unknown_position(client, db_session):
    response = client.post(
        "/jobs",
        data={"title": "공고", "position": "우주비행사", "raw_text": "[자격요건]\nPython"},
    )
    assert response.status_code == 422
    assert "알 수 없는 직무" in response.text
    assert db_session.query(JobPosting).count() == 0


def test_job_form_accepts_legacy_korean_labels(client, db_session):
    # 오래된 폼/북마크에서 온 한국어 라벨 POST 도 코드로 정규화해 받는다.
    response = client.post(
        "/jobs",
        data={
            "title": "공고", "position": "백엔드 개발자",
            "raw_text": "[자격요건]\nPython", "status": "지원완료",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    job = db_session.query(JobPosting).one()
    assert job.position == "backend"
    assert job.status == "applied"


def test_quick_status_update_redirects_with_flash(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="x", status="interest")

    response = client.post(f"/jobs/{job.id}/status", data={"status": "doc_pass"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/jobs/{job.id}?msg=job_status_updated"
    db_session.refresh(job)
    assert job.status == "doc_pass"


def test_status_change_records_an_application_event(client, db_session, job_factory):
    from app.services.application_log import events_for_job

    job = job_factory(status="interest")
    client.post(f"/jobs/{job.id}/status", data={"status": "doc_pass"}, follow_redirects=False)
    client.post(f"/jobs/{job.id}/status", data={"status": "doc_pass"}, follow_redirects=False)  # no-op

    events = events_for_job(db_session, job.id)
    assert [(e.from_status, e.to_status) for e in events] == [("interest", "doc_pass")]


def test_deleting_a_job_removes_its_events(client, db_session, job_factory):
    from app.services.application_log import events_for_job

    job = job_factory(status="interest")
    client.post(f"/jobs/{job.id}/status", data={"status": "applied"}, follow_redirects=False)
    client.post(f"/jobs/{job.id}/interview", data={"event_at": "2026-12-01", "detail": "1차"}, follow_redirects=False)
    assert events_for_job(db_session, job.id)

    client.post(f"/jobs/{job.id}/delete", follow_redirects=False)
    assert events_for_job(db_session, job.id) == []


def test_add_interview_rejects_bad_date(client, job_factory):
    job = job_factory()
    r = client.post(f"/jobs/{job.id}/interview", data={"event_at": "2026/12/01"}, follow_redirects=False)
    assert r.headers["location"] == f"/jobs/{job.id}?msg=job_application_invalid"


def test_quick_status_update_missing_job_redirects(client):
    response = client.post("/jobs/99999/status", data={"status": "interview"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_quick_status_update_rejects_unknown_status(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="x", status="interest")

    response = client.post(
        f"/jobs/{job.id}/status", data={"status": "이상한값"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/jobs/{job.id}?msg=job_status_invalid"
    db_session.refresh(job)
    assert job.status == "interest"


def test_update_job_validation_error_keeps_submitted_values(client, db_session, job_factory):
    job = job_factory(title="원래 제목", raw_text="자격요건\nPython")

    response = client.post(
        f"/jobs/{job.id}/edit",
        data={"title": "", "company": "새 회사명", "position": "backend", "raw_text": ""},
    )
    assert response.status_code == 422
    assert "새 회사명" in response.text  # submitted value re-rendered, not the stored one
    db_session.refresh(job)
    assert job.title == "원래 제목"  # nothing persisted


def test_update_job_application_saves_all_fields(client, db_session, job_factory, resume_factory):
    resume = resume_factory(label="지원용 이력서", raw_text="x", extracted_skills=[])
    job = job_factory(title="공고", raw_text="x", status="interest")

    response = client.post(
        f"/jobs/{job.id}/application",
        data={
            "status": "interview",
            "applied_via": "linkedin",
            "applied_at": "2026-08-01",
            "applied_resume_id": resume.id,
            "memo": "리크루터 김OO",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/jobs/{job.id}?msg=job_application_saved"
    db_session.refresh(job)
    assert job.status == "interview"
    assert job.applied_via == "linkedin"
    assert job.applied_at == "2026-08-01"
    assert job.applied_resume_id == resume.id
    assert job.memo == "리크루터 김OO"


def test_update_job_application_rejects_unknown_channel(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="x", status="interest")

    response = client.post(
        f"/jobs/{job.id}/application", data={"applied_via": "이상한채널"}, follow_redirects=False
    )
    assert response.headers["location"] == f"/jobs/{job.id}?msg=job_application_invalid"
    db_session.refresh(job)
    assert job.applied_via == ""


def test_update_job_application_rejects_bad_date(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="x", status="interest")

    response = client.post(
        f"/jobs/{job.id}/application", data={"applied_at": "2026/01/01"}, follow_redirects=False
    )
    assert response.headers["location"] == f"/jobs/{job.id}?msg=job_application_invalid"


def test_update_job_application_unknown_job(client):
    response = client.post("/jobs/99999/application", data={"status": "interview"}, follow_redirects=False)
    assert response.headers["location"] == "/jobs?msg=job_not_found"


def test_update_job_application_stamps_today_for_applied(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="x", status="interest")

    client.post(
        f"/jobs/{job.id}/application", data={"status": "applied"}, follow_redirects=False
    )
    db_session.refresh(job)
    assert job.applied_at == date.today().isoformat()


def test_job_detail_suggests_channel_from_source_site(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="x", source_site="원티드")

    response = client.get(f"/jobs/{job.id}")
    assert response.status_code == 200
    assert '<option value="wanted" selected>원티드</option>' in response.text


def test_job_detail_handles_deleted_applied_resume(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="x", applied_resume_id=999)

    response = client.get(f"/jobs/{job.id}")
    assert response.status_code == 200
    assert "삭제되었습니다" in response.text


def test_create_job_with_inbound_checkbox(client, db_session):
    client.post(
        "/jobs",
        data={
            "title": "인바운드 공고",
            "position": "backend",
            "raw_text": "[자격요건]\nPython",
            "is_inbound": "on",
        },
        follow_redirects=False,
    )
    job = db_session.query(JobPosting).one()
    assert job.is_inbound is True


def test_create_job_without_inbound_defaults_false(client, db_session):
    client.post(
        "/jobs",
        data={"title": "일반 공고", "position": "backend", "raw_text": "[자격요건]\nPython"},
        follow_redirects=False,
    )
    job = db_session.query(JobPosting).one()
    assert job.is_inbound is False


def test_edit_job_can_turn_inbound_off(client, db_session, job_factory):
    job = job_factory(title="공고", raw_text="자격요건\nPython", is_inbound=True)

    client.post(
        f"/jobs/{job.id}/edit",
        data={"title": "공고", "position": "backend", "raw_text": "[자격요건]\nPython"},
        follow_redirects=False,
    )
    db_session.refresh(job)
    assert job.is_inbound is False


def test_preview_job_returns_parsed_fields(client):
    response = client.post("/jobs/preview", data={"raw_text": "[자격요건]\nPython, FastAPI 경험"})
    assert response.status_code == 200
    body = response.json()
    assert "Python" in body["required_skills"]


def test_guess_source_returns_site_name(client):
    response = client.post("/jobs/guess-source", data={"url": "https://www.wanted.co.kr/wd/1"})
    assert response.status_code == 200
    assert response.json() == {"source_site": "원티드"}
