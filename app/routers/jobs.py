import re
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import (
    JOB_NOT_FOUND_DETAIL,
    JOB_STATUS_INVALID_DETAIL,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MESSAGE,
)
from app.db import get_db
from app.enums import APPLY_CHANNEL, EXPERIENCE_LEVEL, JOB_STATUS, JOB_STATUS_DEFAULT, POSITION
from app.models import JobPosting, Resume
from app.routers._common import get_or_404
from app.services.job_parser import (
    apply_parsed_sections,
    guess_posting_fields,
    guess_source_site,
    normalize_newlines,
    parse_job_posting,
)
from app.services.ocr import extract_text_from_image
from app.services.validation import require_fields
from app.templates import templates

router = APIRouter(prefix="/jobs", tags=["jobs"])

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _suggested_channel(source_site: str) -> str:
    """자유 입력 source_site 문자열에서 지원 채널 코드를 추천한다 (없으면 "")."""
    site = (source_site or "").lower()
    for member in APPLY_CHANNEL:
        if any(key.lower() in site for key in member.meta.get("source_site_keys", ())):
            return member.code
    return ""

_JOB_REQUIRED_FIELD_MESSAGES = {
    "title": "공고 제목을 입력해주세요.",
    "position": "직무를 선택해주세요.",
    "raw_text": "공고 원문을 입력해주세요.",
}

_JOB_FORM_FIELDS = (
    "title", "company", "address", "url", "source_site",
    "position", "experience_level", "status", "raw_text", "is_inbound",
)


class JobForm:
    """The job create/edit form's 10 fields as a single FastAPI dependency.

    Spelled out once here instead of repeated as Form(...) params in both
    create_job and update_job plus an error-render values dict.
    """

    def __init__(
        self,
        title: str = Form(""),
        company: str = Form(""),
        address: str = Form(""),
        url: str = Form(""),
        source_site: str = Form(""),
        position: str = Form(""),
        experience_level: str = Form(""),
        status: str = Form(""),
        raw_text: str = Form(""),
        is_inbound: str = Form(""),
    ):
        self.title = title
        self.company = company
        self.address = address
        self.url = url
        self.source_site = source_site
        # 코드값·(구)라벨 어느 쪽으로 들어와도 코드로 정규화한다. experience_level 은
        # "2~8년" 같은 자유 입력 범위도 허용하므로 미상이면 원문을 그대로 둔다.
        self.position = POSITION.normalize(position) or position.strip()
        self.experience_level = EXPERIENCE_LEVEL.normalize(experience_level) or experience_level.strip()
        self.status = JOB_STATUS.normalize(status) or status.strip()
        self.raw_text = raw_text
        # 체크박스는 체크 시 "on", 미체크 시 미전송. 문자열로 받아 명시적으로 bool 로.
        self.is_inbound = bool(is_inbound)

    def as_dict(self) -> dict:
        return {name: getattr(self, name) for name in _JOB_FORM_FIELDS}

    def validation_errors(self) -> dict:
        errors = require_fields(
            {"title": self.title, "position": self.position, "raw_text": self.raw_text},
            _JOB_REQUIRED_FIELD_MESSAGES,
        )
        # 비어 있으면 OK (_persist_job 가 기본값으로 채움). 값이 있는데 알려진
        # 코드가 아니면 조작됐거나 오래된 폼에서 온 POST 다.
        if self.position and not POSITION.has(self.position):
            errors["position"] = "알 수 없는 직무입니다."
        if self.status and not JOB_STATUS.has(self.status):
            errors["status"] = JOB_STATUS_INVALID_DETAIL
        return errors


def _persist_job(job: JobPosting, form: JobForm) -> None:
    """Write validated form fields + re-parsed sections onto `job`. Caller commits."""
    raw_text = normalize_newlines(form.raw_text)
    job.title = form.title
    job.company = form.company
    job.address = form.address
    job.url = form.url
    job.source_site = form.source_site.strip() or guess_source_site(form.url)
    job.position = form.position
    job.experience_level = form.experience_level
    job.status = form.status or JOB_STATUS_DEFAULT
    job.is_inbound = form.is_inbound
    job.raw_text = raw_text
    apply_parsed_sections(job, parse_job_posting(raw_text))


def _render_job_form(request: Request, template: str, form: JobForm, errors: dict, job=None):
    return templates.TemplateResponse(
        request,
        template,
        {"job": job, "errors": errors, "values": form.as_dict()},
        status_code=422,
    )


@router.get("/new")
def new_job_form(request: Request):
    return templates.TemplateResponse(request, "job_new.html", {})


@router.post("/preview")
def preview_job(raw_text: str = Form(...)):
    raw_text = normalize_newlines(raw_text)
    parsed = parse_job_posting(raw_text)
    guessed = guess_posting_fields(raw_text)
    return {
        "required_skills": parsed.required_skills,
        "preferred_skills": parsed.preferred_skills,
        "title": guessed.title,
        "company": guessed.company,
        "position": guessed.position,
        "experience_level": guessed.experience_level,
        "address": guessed.address,
    }


@router.post("/guess-source")
def guess_source(url: str = Form("")):
    return {"source_site": guess_source_site(url)}


@router.post("/ocr")
async def ocr_job_image(file: UploadFile):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=MAX_UPLOAD_MESSAGE)
    try:
        text = extract_text_from_image(content)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"text": text}


@router.post("")
def create_job(request: Request, form: JobForm = Depends(), db: Session = Depends(get_db)):
    errors = form.validation_errors()
    if errors:
        return _render_job_form(request, "job_new.html", form, errors)

    job = JobPosting()
    _persist_job(job, form)
    db.add(job)
    db.commit()
    db.refresh(job)
    return RedirectResponse(url=f"/jobs/{job.id}?msg=job_created", status_code=303)


@router.get("")
def list_jobs(
    request: Request,
    position: list[str] = Query([]),
    skill: list[str] = Query([]),
    experience_level: list[str] = Query([]),
    region: list[str] = Query([]),
    status: list[str] = Query([]),
    db: Session = Depends(get_db),
):
    all_jobs = list(db.scalars(select(JobPosting).order_by(JobPosting.created_at.desc())))

    jobs = all_jobs
    if position:
        jobs = [j for j in jobs if j.position in position]
    if experience_level:
        jobs = [j for j in jobs if j.experience_level in experience_level]
    if status:
        jobs = [j for j in jobs if j.status in status]
    if skill:
        jobs = [
            j for j in jobs
            if any(s in (j.required_skills or []) or s in (j.preferred_skills or []) for s in skill)
        ]
    if region:
        jobs = [j for j in jobs if any(r in (j.address or "") for r in region)]

    all_skills = sorted({
        s for j in all_jobs
        for s in (j.required_skills or []) + (j.preferred_skills or [])
    })

    return templates.TemplateResponse(
        request,
        "jobs_list.html",
        {
            "jobs": jobs,
            "all_skills": all_skills,
            "filters": {
                "position": position,
                "skill": skill,
                "experience_level": experience_level,
                "region": region,
                "status": status,
            },
            "active_filter_count": (
                len(position) + len(skill) + len(experience_level) + len(region) + len(status)
            ),
        },
    )


@router.get("/{job_id}")
def job_detail(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = get_or_404(db, JobPosting, job_id, JOB_NOT_FOUND_DETAIL)
    resumes = list(db.scalars(select(Resume).order_by(Resume.created_at.desc())))
    applied_resume = db.get(Resume, job.applied_resume_id) if job.applied_resume_id else None
    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "job": job,
            "sections_detected": job.sections_detected,
            "resumes": resumes,
            "suggested_channel": _suggested_channel(job.source_site),
            "applied_resume": applied_resume,
        },
    )


@router.get("/{job_id}/edit")
def edit_job_form(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = get_or_404(db, JobPosting, job_id, JOB_NOT_FOUND_DETAIL)
    return templates.TemplateResponse(request, "job_edit.html", {"job": job})


@router.post("/{job_id}/edit")
def update_job(job_id: int, request: Request, form: JobForm = Depends(), db: Session = Depends(get_db)):
    job = get_or_404(db, JobPosting, job_id, JOB_NOT_FOUND_DETAIL)

    errors = form.validation_errors()
    if errors:
        return _render_job_form(request, "job_edit.html", form, errors, job=job)

    _persist_job(job, form)
    db.commit()
    return RedirectResponse(url=f"/jobs/{job_id}?msg=job_updated", status_code=303)


@router.post("/{job_id}/status")
def update_job_status(job_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)
    if job is None:
        return RedirectResponse(url="/jobs?msg=job_not_found", status_code=303)
    code = JOB_STATUS.normalize(status)
    if code is None:
        return RedirectResponse(url=f"/jobs/{job_id}?msg=job_status_invalid", status_code=303)
    job.status = code
    db.commit()
    return RedirectResponse(url=f"/jobs/{job_id}?msg=job_status_updated", status_code=303)


@router.post("/{job_id}/application")
def update_job_application(
    job_id: int,
    status: str = Form(""),
    applied_via: str = Form(""),
    applied_at: str = Form(""),
    applied_resume_id: int = Form(0),
    memo: str = Form(""),
    db: Session = Depends(get_db),
):
    """지원 상태 + 지원 경로 + 지원일 + 사용한 이력서 + 메모를 한 번에 저장한다.

    빠른 상태 변경 전용인 POST /jobs/{id}/status 는 그대로 두고, 상세 페이지의 "지원 기록"
    폼이 이 엔드포인트를 쓴다.
    """
    job = db.get(JobPosting, job_id)
    if job is None:
        return RedirectResponse(url="/jobs?msg=job_not_found", status_code=303)

    applied_at = applied_at.strip()
    status_code = JOB_STATUS.normalize(status) if status else ""
    channel_code = APPLY_CHANNEL.normalize(applied_via) if applied_via else ""
    if status and status_code is None:
        return RedirectResponse(url=f"/jobs/{job_id}?msg=job_status_invalid", status_code=303)
    if applied_via and channel_code is None:
        return RedirectResponse(url=f"/jobs/{job_id}?msg=job_application_invalid", status_code=303)
    if applied_at and not _ISO_DATE.match(applied_at):
        return RedirectResponse(url=f"/jobs/{job_id}?msg=job_application_invalid", status_code=303)

    if status_code:
        job.status = status_code
    job.applied_via = channel_code or ""
    job.applied_resume_id = applied_resume_id or 0
    job.memo = memo
    # 편의: 날짜 없이 "지원완료"(awaiting) 상태로 표시하면 오늘 날짜를 찍어준다.
    current = JOB_STATUS.get(job.status)
    if current and current.meta.get("awaiting") and not applied_at:
        applied_at = date.today().isoformat()
    job.applied_at = applied_at
    db.commit()
    return RedirectResponse(url=f"/jobs/{job_id}?msg=job_application_saved", status_code=303)


@router.post("/{job_id}/delete")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)
    if job is None:
        return RedirectResponse(url="/jobs?msg=job_not_found", status_code=303)
    db.delete(job)
    db.commit()
    return RedirectResponse(url="/jobs?msg=job_deleted", status_code=303)
