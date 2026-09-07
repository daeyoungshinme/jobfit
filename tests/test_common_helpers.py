"""app/routers/_common.py 의 리소스 로딩 / 상태 검증 헬퍼 단위 테스트."""

from app.routers._common import (
    load_job,
    load_resume,
    load_resume_and_job,
    normalize_job_status,
)


def test_load_job_blank_id_redirects_unless_optional(db_session):
    job, redirect = load_job(db_session, 0)
    assert job is None and redirect.status_code == 303
    assert redirect.headers["location"] == "/jobs?msg=job_not_found"

    job, redirect = load_job(db_session, 0, optional=True)
    assert job is None and redirect is None


def test_load_job_unknown_id_redirects_even_when_optional(db_session):
    job, redirect = load_job(db_session, 99999, optional=True)
    assert job is None and redirect.headers["location"] == "/jobs?msg=job_not_found"


def test_load_resume_blank_and_unknown(db_session):
    _, redirect = load_resume(db_session, 0)
    assert redirect.headers["location"] == "/resumes?msg=resume_not_found"
    _, redirect = load_resume(db_session, 0, optional=True)
    assert redirect is None


def test_load_resume_and_job_resume_checked_first(db_session, job_factory):
    job = job_factory()
    _, _, redirect = load_resume_and_job(db_session, 0, job.id)
    assert redirect.headers["location"] == "/resumes?msg=resume_not_found"


def test_load_resume_and_job_job_optional(db_session, resume_factory):
    resume = resume_factory()
    r, j, redirect = load_resume_and_job(db_session, resume.id, 0, job_optional=True)
    assert r is resume and j is None and redirect is None


def test_normalize_job_status():
    assert normalize_job_status("") == ""
    assert normalize_job_status("interview") == "interview"
    assert normalize_job_status("면접") == "interview"
    assert normalize_job_status("이상한값") is None
