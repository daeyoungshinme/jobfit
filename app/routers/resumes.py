from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MESSAGE,
    RESUME_NOT_FOUND_DETAIL,
    UPLOAD_NO_TEXT_MESSAGE,
)
from app.db import get_db
from app.models import JobPosting, Resume
from app.routers._common import ResumeContentForm, get_or_404
from app.services.resume_editor import apply_resume_content, new_resume, validate_resume_content
from app.services.resume_parser import extract_text_from_upload
from app.services.resume_reviewer import review_resume
from app.services.validation import require_fields
from app.templates import templates

router = APIRouter(prefix="/resumes", tags=["resumes"])

_RESUME_REQUIRED_FIELD_MESSAGES = {"label": "이력서 이름을 입력해주세요."}


@router.get("/new")
def new_resume_form(request: Request):
    return templates.TemplateResponse(request, "resume_new.html", {})


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
    if len(content) > MAX_UPLOAD_BYTES:
        errors["file"] = MAX_UPLOAD_MESSAGE
    elif not errors:
        try:
            raw_text = extract_text_from_upload(file.filename, content)
        except ValueError as exc:
            errors["file"] = str(exc)
        else:
            if not raw_text.strip():
                errors["file"] = UPLOAD_NO_TEXT_MESSAGE

    if errors:
        return templates.TemplateResponse(
            request,
            "resume_new.html",
            {"errors": errors, "values": {"label": label}, "active_tab": "file-tab"},
            status_code=422,
        )

    resume = new_resume(
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
    form: ResumeContentForm = Depends(),
    db: Session = Depends(get_db),
):
    errors = require_fields({"label": form.label}, _RESUME_REQUIRED_FIELD_MESSAGES)
    errors.update(validate_resume_content("form", **form.content_kwargs()))
    if errors:
        return templates.TemplateResponse(
            request,
            "resume_new.html",
            {"errors": errors, "values": form.error_values(), "active_tab": "form-tab"},
            status_code=422,
        )

    resume = new_resume(label=form.label, source_type="form", **form.content_kwargs())
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return RedirectResponse(url=f"/resumes/{resume.id}?msg=resume_created", status_code=303)


@router.get("")
def list_resumes(request: Request, db: Session = Depends(get_db)):
    resumes = list(db.scalars(select(Resume).order_by(Resume.created_at.desc())))
    return templates.TemplateResponse(request, "resumes_list.html", {"resumes": resumes})


@router.get("/{resume_id}")
def resume_detail(resume_id: int, request: Request, db: Session = Depends(get_db)):
    resume = get_or_404(db, Resume, resume_id, RESUME_NOT_FOUND_DETAIL)
    suggestions = review_resume(resume.raw_text, len(resume.extracted_skills or []))
    jobs = list(db.scalars(select(JobPosting).order_by(JobPosting.created_at.desc())))
    return templates.TemplateResponse(
        request,
        "resume_detail.html",
        {"resume": resume, "suggestions": suggestions, "jobs": jobs},
    )


@router.get("/{resume_id}/edit")
def edit_resume_form(resume_id: int, request: Request, db: Session = Depends(get_db)):
    resume = get_or_404(db, Resume, resume_id, RESUME_NOT_FOUND_DETAIL)
    return templates.TemplateResponse(request, "resume_edit.html", {"resume": resume})


@router.post("/{resume_id}/edit")
def update_resume(
    resume_id: int,
    request: Request,
    form: ResumeContentForm = Depends(),
    db: Session = Depends(get_db),
):
    resume = get_or_404(db, Resume, resume_id, RESUME_NOT_FOUND_DETAIL)

    errors = require_fields({"label": form.label}, _RESUME_REQUIRED_FIELD_MESSAGES)
    errors.update(validate_resume_content(resume.source_type, **form.content_kwargs()))
    if errors:
        return templates.TemplateResponse(
            request,
            "resume_edit.html",
            {"resume": resume, "errors": errors, "values": form.error_values()},
            status_code=422,
        )

    resume.label = form.label
    apply_resume_content(resume, **form.content_kwargs())
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
