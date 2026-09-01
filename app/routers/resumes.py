from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobPosting, Resume
from app.services.resume_editor import (
    apply_resume_content,
    compose_form_raw_text,
    validate_resume_content,
)
from app.services.resume_parser import extract_text_from_upload
from app.services.resume_reviewer import review_resume
from app.services.skill_extractor import extract_skill_names
from app.services.validation import require_fields
from app.templates import templates

router = APIRouter(prefix="/resumes", tags=["resumes"])

_RESUME_REQUIRED_FIELD_MESSAGES = {"label": "이력서 이름을 입력해주세요."}


def _build_resume(*, label: str, source_type: str, raw_text: str, structured: dict) -> Resume:
    return Resume(
        label=label,
        source_type=source_type,
        raw_text=raw_text,
        structured=structured,
        extracted_skills=extract_skill_names(raw_text),
    )


@router.get("/new")
def new_resume_form(request: Request):
    return templates.TemplateResponse("resume_new.html", {"request": request})


@router.post("/upload")
async def upload_resume(
    request: Request,
    label: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    errors = require_fields({"label": label}, _RESUME_REQUIRED_FIELD_MESSAGES)
    content = await file.read()
    raw_text = ""
    try:
        raw_text = extract_text_from_upload(file.filename, content)
    except ValueError as exc:
        errors["file"] = str(exc)

    if errors:
        return templates.TemplateResponse(
            "resume_new.html",
            {
                "request": request,
                "errors": errors,
                "values": {"label": label},
                "active_tab": "file-tab",
            },
            status_code=422,
        )

    resume = _build_resume(
        label=label,
        source_type="file",
        raw_text=raw_text,
        structured={"original_filename": file.filename},
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return RedirectResponse(url=f"/resumes/{resume.id}?msg=resume_uploaded", status_code=303)


@router.post("/form")
def submit_resume_form(
    request: Request,
    label: str = Form(""),
    career: str = Form(""),
    projects: str = Form(""),
    education: str = Form(""),
    skills_text: str = Form(""),
    db: Session = Depends(get_db),
):
    errors = require_fields({"label": label}, _RESUME_REQUIRED_FIELD_MESSAGES)
    if errors:
        return templates.TemplateResponse(
            "resume_new.html",
            {
                "request": request,
                "errors": errors,
                "values": {
                    "label": label,
                    "career": career,
                    "projects": projects,
                    "education": education,
                    "skills_text": skills_text,
                },
                "active_tab": "form-tab",
            },
            status_code=422,
        )

    raw_text = compose_form_raw_text(career, projects, education, skills_text)
    resume = _build_resume(
        label=label,
        source_type="form",
        raw_text=raw_text,
        structured={
            "career": career,
            "projects": projects,
            "education": education,
            "skills_text": skills_text,
        },
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return RedirectResponse(url=f"/resumes/{resume.id}?msg=resume_created", status_code=303)


@router.get("")
def list_resumes(request: Request, db: Session = Depends(get_db)):
    resumes = list(db.scalars(select(Resume).order_by(Resume.created_at.desc())))
    return templates.TemplateResponse("resumes_list.html", {"request": request, "resumes": resumes})


@router.get("/{resume_id}")
def resume_detail(resume_id: int, request: Request, db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="이력서를 찾을 수 없습니다")
    suggestions = review_resume(resume.raw_text, len(resume.extracted_skills or []))
    jobs = list(db.scalars(select(JobPosting).order_by(JobPosting.created_at.desc())))
    return templates.TemplateResponse(
        "resume_detail.html",
        {"request": request, "resume": resume, "suggestions": suggestions, "jobs": jobs},
    )


@router.get("/{resume_id}/edit")
def edit_resume_form(resume_id: int, request: Request, db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="이력서를 찾을 수 없습니다")
    return templates.TemplateResponse("resume_edit.html", {"request": request, "resume": resume})


@router.post("/{resume_id}/edit")
def update_resume(
    resume_id: int,
    request: Request,
    label: str = Form(""),
    raw_text: str = Form(""),
    career: str = Form(""),
    projects: str = Form(""),
    education: str = Form(""),
    skills_text: str = Form(""),
    db: Session = Depends(get_db),
):
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="이력서를 찾을 수 없습니다")

    errors = require_fields({"label": label}, _RESUME_REQUIRED_FIELD_MESSAGES)
    errors.update(validate_resume_content(resume.source_type, raw_text=raw_text))
    if errors:
        resume.label = label
        return templates.TemplateResponse(
            "resume_edit.html",
            {
                "request": request,
                "resume": resume,
                "errors": errors,
                "values": {
                    "raw_text": raw_text,
                    "career": career,
                    "projects": projects,
                    "education": education,
                    "skills_text": skills_text,
                },
            },
            status_code=422,
        )

    resume.label = label
    apply_resume_content(
        resume,
        raw_text=raw_text,
        career=career,
        projects=projects,
        education=education,
        skills_text=skills_text,
    )
    db.commit()
    return RedirectResponse(url=f"/resumes/{resume_id}?msg=resume_updated", status_code=303)


@router.post("/{resume_id}/delete")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.get(Resume, resume_id)
    if resume is None:
        return RedirectResponse(url="/resumes?msg=resume_not_found", status_code=303)
    db.delete(resume)
    db.commit()
    return RedirectResponse(url="/resumes?msg=resume_deleted", status_code=303)
