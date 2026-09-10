from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STALE_AFTER_DAYS
from app.db import get_db
from app.models import JobPosting, Resume
from app.routers._common import ResumeContentForm, list_all, load_resume_and_job
from app.services import application_log
from app.services.activity_report import build_activity_report
from app.services.interview_prep import build_interview_prep
from app.services.job_fit_coach import build_coaching
from app.services.matcher import MatchConfig, rank_matches, scarcity_weights, skill_ranking
from app.services.profile_exporter import build_platform_profiles
from app.services.resume_editor import apply_resume_content, validate_resume_content
from app.services.resume_sections import detect_sections
from app.templates import templates

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/dashboard")
def dashboard(
    request: Request,
    resume_id: int = 0,
    position: str = "",
    axes: int = 0,
    db: Session = Depends(get_db),
):
    resumes = list_all(db, Resume)
    query = select(JobPosting).order_by(JobPosting.created_at.desc())
    if position:
        query = query.where(JobPosting.position == position)
    jobs = list(db.scalars(query))
    ranking = skill_ranking(jobs)

    matches = []
    selected_resume = None
    if resume_id:
        selected_resume = db.get(Resume, resume_id)
        if selected_resume:
            # 희소 스킬 미보유에 더 큰 감점을 주고, ?axes=1 이면 경력·직무 적합도
            # 축을 최종 점수에 섞는다 (기본값은 투명 노출만).
            config = MatchConfig(axes_weight=0.25) if axes else MatchConfig()
            matches = rank_matches(
                selected_resume.extracted_skills or [], jobs,
                config=config,
                skill_weights=scarcity_weights(ranking),
                resume=selected_resume,
            )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "resumes": resumes,
            "selected_resume": selected_resume,
            "selected_position": position,
            "axes_on": bool(axes),
            "matches": matches,
            "ranking": ranking,
            "job_count": len(jobs),
        },
    )


@router.get("/activity")
def activity(request: Request, db: Session = Depends(get_db)):
    jobs = list_all(db, JobPosting)
    interview_events = application_log.all_interview_events(db)
    return templates.TemplateResponse(
        request,
        "activity.html",
        {
            "report": build_activity_report(jobs, interview_events=interview_events),
            "STALE_AFTER_DAYS": STALE_AFTER_DAYS,
        },
    )


@router.get("/profile")
def profile(request: Request, resume_id: int = 0, db: Session = Depends(get_db)):
    resumes = list_all(db, Resume)
    selected_resume = db.get(Resume, resume_id) if resume_id else None
    bundle = None
    if selected_resume:
        demand = [rank.name for rank in skill_ranking(list_all(db, JobPosting))]
        bundle = build_platform_profiles(selected_resume, skill_demand=demand)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "resumes": resumes,
            "selected_resume": selected_resume,
            "bundle": bundle,
        },
    )


@router.get("/coach")
def coach(request: Request, resume_id: int = 0, job_id: int = 0, db: Session = Depends(get_db)):
    resume, job, redirect = load_resume_and_job(db, resume_id, job_id)
    if redirect:
        return redirect

    coaching = build_coaching(
        resume.extracted_skills or [], job,
        resume_text=resume.raw_text, resume_sections=detect_sections(resume),
        resume=resume,
    )
    return templates.TemplateResponse(
        request,
        "coach.html",
        {
            "resume": resume,
            "job": job,
            "coaching": coaching,
        },
    )


@router.get("/interview")
def interview(request: Request, resume_id: int = 0, job_id: int = 0, db: Session = Depends(get_db)):
    # job 은 선택 — 이력서 단독 면접 준비 모드를 허용한다.
    resume, job, redirect = load_resume_and_job(db, resume_id, job_id, job_optional=True)
    if redirect:
        return redirect

    prep = build_interview_prep(resume, job)
    return templates.TemplateResponse(
        request,
        "interview.html",
        {
            "resume": resume,
            "job": job,
            "prep": prep,
        },
    )


def _render_tailor(request, resume, job, *, errors=None, values=None, status_code=200):
    coaching = build_coaching(
        resume.extracted_skills or [], job,
        resume_text=resume.raw_text, resume_sections=detect_sections(resume),
        resume=resume,
    )
    return templates.TemplateResponse(
        request,
        "tailor.html",
        {
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
    resume, job, redirect = load_resume_and_job(db, resume_id, job_id)
    if redirect:
        return redirect
    return _render_tailor(request, resume, job)


@router.post("/tailor")
def save_tailored_resume(
    request: Request,
    resume_id: int = 0,
    job_id: int = 0,
    form: ResumeContentForm = Depends(),
    db: Session = Depends(get_db),
):
    resume, job, redirect = load_resume_and_job(db, resume_id, job_id)
    if redirect:
        return redirect

    errors = validate_resume_content(resume.source_type, **form.content_kwargs())
    if errors:
        return _render_tailor(
            request, resume, job, errors=errors, values=form.content_kwargs(), status_code=422
        )

    apply_resume_content(resume, **form.content_kwargs())
    db.commit()
    return RedirectResponse(
        url=f"/analysis/tailor?resume_id={resume_id}&job_id={job_id}&msg=resume_updated",
        status_code=303,
    )
