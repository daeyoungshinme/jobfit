from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.constants import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MESSAGE,
    RESUME_NOT_FOUND_DETAIL,
    UPLOAD_NO_TEXT_MESSAGE,
)
from app.db import get_db
from app.models import JobPosting, Resume
from app.routers._common import (
    LABEL_REQUIRED_MESSAGE,
    ResumeContentForm,
    get_or_404,
    list_all,
    load_resume,
)
from app.services.job_parser import guess_position_code
from app.services.profile_exporter import guess_total_years
from app.services.resume_editor import apply_resume_content, new_resume
from app.services.resume_parser import extract_text_from_upload
from app.services.resume_reviewer import review_resume
from app.services.resume_sections import detect_sections
from app.services.validation import require_fields
from app.templates import templates

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _render_resume_form(request, template, *, errors, values, resume=None, active_tab=None):
    ctx = {"errors": errors, "values": values}
    if resume is not None:
        ctx["resume"] = resume
    if active_tab:
        ctx["active_tab"] = active_tab
    return templates.TemplateResponse(request, template, ctx, status_code=422)


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
    errors = require_fields({"label": label}, LABEL_REQUIRED_MESSAGE)
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
        return _render_resume_form(
            request, "resume_new.html",
            errors=errors, values={"label": label}, active_tab="file-tab",
        )

    resume = new_resume(
        label=label,
        source_type="file",
        raw_text=raw_text,
        total_years=str(guess_total_years(raw_text) or ""),
        target_position=guess_position_code(label, raw_text),
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
    errors = form.validation_errors("form")
    if errors:
        return _render_resume_form(
            request, "resume_new.html",
            errors=errors, values=form.error_values(), active_tab="form-tab",
        )

    resume = new_resume(label=form.label, source_type="form", **form.content_kwargs())
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return RedirectResponse(url=f"/resumes/{resume.id}?msg=resume_created", status_code=303)


@router.get("")
def list_resumes(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "resumes_list.html", {"resumes": list_all(db, Resume)}
    )


@router.get("/{resume_id}")
def resume_detail(resume_id: int, request: Request, db: Session = Depends(get_db)):
    resume = get_or_404(db, Resume, resume_id, RESUME_NOT_FOUND_DETAIL)
    suggestions = review_resume(
        resume.raw_text, len(resume.extracted_skills or []), sections=detect_sections(resume)
    )
    return templates.TemplateResponse(
        request,
        "resume_detail.html",
        {"resume": resume, "suggestions": suggestions, "jobs": list_all(db, JobPosting)},
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

    errors = form.validation_errors(resume.source_type)
    if errors:
        return _render_resume_form(
            request, "resume_edit.html",
            errors=errors, values=form.error_values(), resume=resume,
        )

    resume.label = form.label
    apply_resume_content(resume, **form.content_kwargs())
    db.commit()
    return RedirectResponse(url=f"/resumes/{resume_id}?msg=resume_updated", status_code=303)


@router.post("/{resume_id}/delete")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    resume, redirect = load_resume(db, resume_id)
    if redirect:
        return redirect
    db.delete(resume)
    db.commit()
    return RedirectResponse(url="/resumes?msg=resume_deleted", status_code=303)
