"""Shared job-posting write path — the counterpart to `resume_editor.py`.

`jobs.py::JobForm` (a FastAPI `Form(...)` dependency) binds and enum-normalizes
the raw request fields; everything past that — domain validation, and writing
the validated fields + re-parsed sections onto a `JobPosting` — lives here so
create and edit stay in lock-step and the router keeps no business logic.
"""

from app.constants import JOB_STATUS_INVALID_DETAIL, MAX_RAW_TEXT_CHARS, MAX_RAW_TEXT_MESSAGE
from app.enums import APPLY_CHANNEL, JOB_STATUS, JOB_STATUS_DEFAULT, POSITION
from app.models import JobPosting
from app.services.job_parser import (
    apply_parsed_sections,
    guess_posting_fields,
    guess_source_site,
    normalize_newlines,
    parse_job_posting,
)
from app.services.validation import require_fields

_REQUIRED_FIELD_MESSAGES = {
    "title": "공고 제목을 입력해주세요.",
    "position": "직무를 선택해주세요.",
    "raw_text": "공고 원문을 입력해주세요.",
}


def validate_job_content(*, title: str, position: str, status: str, raw_text: str, **_ignored) -> dict:
    """Field errors for a job-posting write, keyed by field name. Empty = OK.

    `JobForm` has already normalized `position` / `status` to codes (or left a
    free-form experience range verbatim); a non-empty value that still isn't a
    known code means the POST was tampered with or came from a stale form.
    """
    errors = require_fields(
        {"title": title, "position": position, "raw_text": raw_text},
        _REQUIRED_FIELD_MESSAGES,
    )
    if position and not POSITION.has(position):
        errors["position"] = "알 수 없는 직무입니다."
    if status and not JOB_STATUS.has(status):
        errors["status"] = JOB_STATUS_INVALID_DETAIL
    # preview 는 초과 시 400 을 준다 — 저장 경로도 같은 상한을 강제한다.
    if len(raw_text) > MAX_RAW_TEXT_CHARS:
        errors["raw_text"] = MAX_RAW_TEXT_MESSAGE
    return errors


def apply_job_content(
    job: JobPosting,
    *,
    title: str = "",
    company: str = "",
    address: str = "",
    url: str = "",
    source_site: str = "",
    position: str = "",
    experience_level: str = "",
    status: str = "",
    raw_text: str = "",
    is_inbound: bool = False,
    employment_type: str = "",
    remote_policy: str = "",
    salary_text: str = "",
    deadline: str = "",
) -> None:
    """Write validated form fields + re-parsed sections onto `job`. Caller commits.

    Form value wins when present; an empty field falls back to a best-effort
    guess from the pasted posting text, so a no-JS user still gets autofill.
    """
    raw_text = normalize_newlines(raw_text)
    guessed = guess_posting_fields(raw_text)
    job.title = title
    job.company = company or guessed.company
    job.address = address or guessed.address
    job.url = url
    job.source_site = source_site.strip() or guess_source_site(url)
    job.position = position
    job.experience_level = experience_level
    job.status = status or JOB_STATUS_DEFAULT
    job.is_inbound = is_inbound
    job.raw_text = raw_text
    apply_parsed_sections(job, parse_job_posting(raw_text))
    job.employment_type = employment_type or guessed.employment_type
    job.remote_policy = remote_policy or guessed.remote_policy
    job.salary_text = salary_text or guessed.salary_text
    job.deadline = deadline or guessed.deadline


def new_job(**fields) -> JobPosting:
    """Build a new JobPosting, routing content through apply_job_content() so
    creation and editing share the same guess/parse/default rules."""
    job = JobPosting()
    apply_job_content(job, **fields)
    return job


def suggest_apply_channel(source_site: str) -> str:
    """자유 입력 source_site 문자열에서 지원 채널 코드를 추천한다 (없으면 "").

    지원 기록 폼(job_detail)의 채널 셀렉트 기본값으로 쓴다.
    """
    site = (source_site or "").lower()
    for member in APPLY_CHANNEL:
        if any(key.lower() in site for key in member.meta.get("source_site_keys", ())):
            return member.code
    return ""
