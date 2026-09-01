from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import POSITIONS
from app.db import get_db
from app.models import JobPosting, Resume
from app.services.job_fit_coach import build_coaching
from app.services.matcher import rank_matches, skill_ranking
from app.services.resume_editor import apply_resume_content, validate_resume_content
from app.templates import templates

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/dashboard")
def dashboard(
    request: Request,
    resume_id: int = 0,
    position: str = "",
    db: Session = Depends(get_db),
):
    resumes = list(db.scalars(select(Resume).order_by(Resume.created_at.desc())))
    query = select(JobPosting)
    if position:
        query = query.where(JobPosting.position == position)
    jobs = list(db.scalars(query))

    matches = []
    selected_resume = None
    if resume_id:
        selected_resume = db.get(Resume, resume_id)
        if selected_resume:
            matches = rank_matches(selected_resume.extracted_skills or [], jobs)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "resumes": resumes,
            "positions": POSITIONS,
            "selected_resume": selected_resume,
            "selected_position": position,
            "matches": matches,
            "ranking": skill_ranking(jobs),
            "job_count": len(jobs),
        },
    )


@router.get("/coach")
def coach(request: Request, resume_id: int = 0, job_id: int = 0, db: Session = Depends(get_db)):
    resume, job, redirect = _load_resume_and_job(db, resume_id, job_id)
    if redirect:
        return redirect

    coaching = build_coaching(resume.extracted_skills or [], job, resume_text=resume.raw_text)
    return templates.TemplateResponse(
        request,
        "coach.html",
        {
            "request": request,
            "resume": resume,
            "job": job,
            "coaching": coaching,
        },
    )


def _load_resume_and_job(db: Session, resume_id: int, job_id: int):
    """Shared guard for the coach/tailor routes — returns (resume, job) or a redirect."""
    resume = db.get(Resume, resume_id) if resume_id else None
    if resume is None:
        return None, None, RedirectResponse(url="/resumes?msg=resume_not_found", status_code=303)
    job = db.get(JobPosting, job_id) if job_id else None
    if job is None:
        return None, None, RedirectResponse(url="/jobs?msg=job_not_found", status_code=303)
    return resume, job, None


def _render_tailor(request, resume, job, *, errors=None, values=None, status_code=200):
    coaching = build_coaching(resume.extracted_skills or [], job, resume_text=resume.raw_text)
    return templates.TemplateResponse(
        request,
        "tailor.html",
        {
            "request": request,
            "resume": resume,
            "job": job,
            "coaching": coaching,
            "structured": values if values is not None else (resume.structured or {}),
            "errors": errors or {},
            "values": values or {},
        },
        status_code=status_code,
    )


@router.get("/tailor")
def tailor(request: Request, resume_id: int = 0, job_id: int = 0, db: Session = Depends(get_db)):
    resume, job, redirect = _load_resume_and_job(db, resume_id, job_id)
    if redirect:
        return redirect
    return _render_tailor(request, resume, job)


@router.post("/tailor")
def save_tailored_resume(
    request: Request,
    resume_id: int = 0,
    job_id: int = 0,
    raw_text: str = Form(""),
    career: str = Form(""),
    projects: str = Form(""),
    education: str = Form(""),
    skills_text: str = Form(""),
    db: Session = Depends(get_db),
):
    resume, job, redirect = _load_resume_and_job(db, resume_id, job_id)
    if redirect:
        return redirect

    errors = validate_resume_content(resume.source_type, raw_text=raw_text)
    if errors:
        values = {
            "raw_text": raw_text,
            "career": career,
            "projects": projects,
            "education": education,
            "skills_text": skills_text,
        }
        return _render_tailor(request, resume, job, errors=errors, values=values, status_code=422)

    apply_resume_content(
        resume,
        raw_text=raw_text,
        career=career,
        projects=projects,
        education=education,
        skills_text=skills_text,
    )
    db.commit()
    return RedirectResponse(
        url=f"/analysis/tailor?resume_id={resume_id}&job_id={job_id}&msg=resume_updated",
        status_code=303,
    )
