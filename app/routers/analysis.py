from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import POSITIONS
from app.db import get_db
from app.models import JobPosting, Resume
from app.services.job_fit_coach import build_coaching
from app.services.matcher import rank_matches, skill_ranking
from app.templates import templates

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/skills")
def skill_stats(request: Request, position: str = "", db: Session = Depends(get_db)):
    query = select(JobPosting)
    if position:
        query = query.where(JobPosting.position == position)
    jobs = list(db.scalars(query))
    ranking = skill_ranking(jobs)

    return templates.TemplateResponse(
        "job_stats.html",
        {
            "request": request,
            "positions": POSITIONS,
            "selected_position": position,
            "job_count": len(jobs),
            "ranking": ranking,
        },
    )


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
        "dashboard.html",
        {
            "request": request,
            "resumes": resumes,
            "positions": POSITIONS,
            "selected_resume": selected_resume,
            "selected_position": position,
            "matches": matches,
        },
    )


@router.get("/coach")
def coach(request: Request, resume_id: int = 0, job_id: int = 0, db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id) if resume_id else None
    if resume is None:
        return RedirectResponse(url="/resumes?msg=resume_not_found", status_code=303)
    job = db.get(JobPosting, job_id) if job_id else None
    if job is None:
        return RedirectResponse(url="/jobs?msg=job_not_found", status_code=303)

    coaching = build_coaching(resume.extracted_skills or [], job)
    return templates.TemplateResponse(
        "coach.html",
        {
            "request": request,
            "resume": resume,
            "job": job,
            "coaching": coaching,
        },
    )
