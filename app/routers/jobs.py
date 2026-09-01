from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import (
    EXPERIENCE_LEVELS,
    JOB_NOT_FOUND_DETAIL,
    JOB_STATUS_DEFAULT,
    JOB_STATUSES,
    POSITIONS,
    REGIONS,
)
from app.db import get_db
from app.models import JobPosting, Resume
from app.services.job_parser import (
    ParsedJobPosting,
    guess_posting_fields,
    guess_source_site,
    normalize_newlines,
    parse_job_posting,
)
from app.services.ocr import extract_text_from_image
from app.services.validation import require_fields
from app.templates import templates

router = APIRouter(prefix="/jobs", tags=["jobs"])

_JOB_REQUIRED_FIELD_MESSAGES = {
    "title": "공고 제목을 입력해주세요.",
    "position": "직무를 선택해주세요.",
    "raw_text": "공고 원문을 입력해주세요.",
}

_JOB_FORM_FIELDS = (
    "title", "company", "address", "url", "source_site",
    "position", "experience_level", "status", "raw_text",
)


class JobForm:
    """The job create/edit form's 9 fields as a single FastAPI dependency.

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
    ):
        self.title = title
        self.company = company
        self.address = address
        self.url = url
        self.source_site = source_site
        self.position = position
        self.experience_level = experience_level
        self.status = status
        self.raw_text = raw_text

    def as_dict(self) -> dict:
        return {name: getattr(self, name) for name in _JOB_FORM_FIELDS}

    def validation_errors(self) -> dict:
        return require_fields(
            {"title": self.title, "position": self.position, "raw_text": self.raw_text},
            _JOB_REQUIRED_FIELD_MESSAGES,
        )


def _apply_parsed_sections(job: JobPosting, parsed: ParsedJobPosting) -> None:
    job.main_tasks = parsed.main_tasks_text
    job.required_text = parsed.required_text
    job.preferred_text = parsed.preferred_text
    job.required_skills = parsed.required_skills
    job.preferred_skills = parsed.preferred_skills


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
    job.raw_text = raw_text
    _apply_parsed_sections(job, parse_job_posting(raw_text))


def _render_job_form(request: Request, template: str, form: JobForm, errors: dict, job=None):
    return templates.TemplateResponse(
        request,
        template,
        {
            "request": request,
            "job": job,
            "positions": POSITIONS,
            "experience_levels": EXPERIENCE_LEVELS,
            "statuses": JOB_STATUSES,
            "errors": errors,
            "values": form.as_dict(),
        },
        status_code=422,
    )


@router.get("/new")
def new_job_form(request: Request):
    return templates.TemplateResponse(
        request,
        "job_new.html",
        {
            "request": request,
            "positions": POSITIONS,
            "experience_levels": EXPERIENCE_LEVELS,
            "statuses": JOB_STATUSES,
        },
    )


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
            "request": request,
            "jobs": jobs,
            "positions": POSITIONS,
            "experience_levels": EXPERIENCE_LEVELS,
            "regions": REGIONS,
            "statuses": JOB_STATUSES,
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
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND_DETAIL)
    sections_detected = parse_job_posting(job.raw_text).sections_detected
    resumes = list(db.scalars(select(Resume).order_by(Resume.created_at.desc())))
    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "request": request,
            "job": job,
            "sections_detected": sections_detected,
            "resumes": resumes,
            "statuses": JOB_STATUSES,
        },
    )


@router.get("/{job_id}/edit")
def edit_job_form(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND_DETAIL)
    return templates.TemplateResponse(
        request,
        "job_edit.html",
        {
            "request": request,
            "job": job,
            "positions": POSITIONS,
            "experience_levels": EXPERIENCE_LEVELS,
            "statuses": JOB_STATUSES,
        },
    )


@router.post("/{job_id}/edit")
def update_job(job_id: int, request: Request, form: JobForm = Depends(), db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND_DETAIL)

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
    if status not in JOB_STATUSES:
        return RedirectResponse(url=f"/jobs/{job_id}?msg=job_status_invalid", status_code=303)
    job.status = status
    db.commit()
    return RedirectResponse(url=f"/jobs/{job_id}?msg=job_status_updated", status_code=303)


@router.post("/{job_id}/delete")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)
    if job is None:
        return RedirectResponse(url="/jobs?msg=job_not_found", status_code=303)
    db.delete(job)
    db.commit()
    return RedirectResponse(url="/jobs?msg=job_deleted", status_code=303)
