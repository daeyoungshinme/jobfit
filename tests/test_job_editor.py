from app.models import JobPosting
from app.services.job_editor import (
    apply_job_content,
    new_job,
    suggest_apply_channel,
    validate_job_content,
)

_OK = dict(title="백엔드 개발자", position="backend", status="interest",
           raw_text="[자격요건]\nPython, Kafka")


def test_validate_requires_title_position_raw_text():
    errors = validate_job_content(title="", position="", status="", raw_text="")
    assert set(errors) == {"title", "position", "raw_text"}


def test_validate_rejects_unknown_codes_and_oversized_text():
    assert "position" in validate_job_content(**{**_OK, "position": "우주비행사"})
    assert "status" in validate_job_content(**{**_OK, "status": "made_up"})
    assert "raw_text" in validate_job_content(**{**_OK, "raw_text": "가" * 50_001})
    assert validate_job_content(**_OK) == {}


def test_validate_allows_free_form_experience_range():
    # position/status 만 코드 검증 — experience_level 은 자유 입력 허용
    assert validate_job_content(**_OK, experience_level="2~8년") == {}


def test_apply_job_content_parses_sections_and_guesses_blanks():
    job = JobPosting()
    apply_job_content(
        job, title="공고", position="backend", status="",
        raw_text="계약직, 완전 재택.\n[자격요건]\nPython\n[복리후생]\n- 맥북",
    )
    assert "Python" in job.required_skills
    assert job.status == "interest"          # 빈 status → 기본값
    assert job.employment_type == "contract"  # 원문에서 추측
    assert job.remote_policy == "remote"
    assert "맥북" in job.benefits_text


def test_apply_job_content_form_value_wins_over_guess():
    job = JobPosting()
    apply_job_content(
        job, title="공고", position="backend", status="applied",
        employment_type="fulltime",
        raw_text="계약직 채용\n[자격요건]\nPython",
    )
    assert job.employment_type == "fulltime"  # 폼 값 우선
    assert job.status == "applied"


def test_new_job_routes_through_apply():
    job = new_job(title="공고", position="backend", status="",
                  raw_text="[자격요건]\nPython")
    assert isinstance(job, JobPosting)
    assert "Python" in job.required_skills


def test_suggest_apply_channel_from_source_site():
    assert suggest_apply_channel("원티드에서 지원") == "wanted"
    assert suggest_apply_channel("saramin.co.kr") == "saramin"
    assert suggest_apply_channel("회사 홈페이지") == ""
