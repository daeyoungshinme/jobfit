"""Shared router helpers: résumé-content form dependency, get-or-404, and the
resource-loading / status-validation helpers used across the job routes.

`ResumeContentForm` bundles the résumé content fields once instead of repeating
the same `Form(...)` params + `apply_resume_content` kwargs + error-render
`values` dict across `resumes.py` (create/edit) and `analysis.py` (tailor save).
Mirrors `jobs.py::JobForm`.

Resource-not-found policy (kept consistent by using these helpers):
  - a **path** parameter (`/jobs/{id}`, `/resumes/{id}`) that doesn't resolve
    is a bad URL → `get_or_404` raises 404 (styled page for browsers).
  - a **query-string** id (`?resume_id=`, `?job_id=`) that's missing/blank/
    unknown is a stale or hand-edited link, not a bad route → `load_job` /
    `load_resume` return a 303 redirect to the relevant list with a flash,
    so the user lands somewhere useful instead of a dead end.
"""

from fastapi import Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.enums import JOB_STATUS
from app.models import JobPosting, Resume

_CONTENT_FIELDS = ("raw_text", "career", "projects", "education", "skills_text")


class ResumeContentForm:
    def __init__(
        self,
        label: str = Form(""),
        raw_text: str = Form(""),
        career: str = Form(""),
        projects: str = Form(""),
        education: str = Form(""),
        skills_text: str = Form(""),
    ):
        self.label = label
        self.raw_text = raw_text
        self.career = career
        self.projects = projects
        self.education = education
        self.skills_text = skills_text

    def content_kwargs(self) -> dict:
        """kwargs for `validate_resume_content` / `apply_resume_content` / `new_resume`."""
        return {name: getattr(self, name) for name in _CONTENT_FIELDS}

    def error_values(self) -> dict:
        """Context for re-rendering a form with validation errors."""
        return {"label": self.label, **self.content_kwargs()}


def get_or_404(db: Session, model, pk, detail: str):
    """Fetch `model` by primary key or raise 404 with `detail`.

    The 404 is rendered as the styled page for browser navigations by the
    handler in `main.py`; API clients still get JSON.
    """
    obj = db.get(model, pk) if pk else None
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def _list_redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def load_job(db: Session, job_id: int, *, optional: bool = False):
    """Return `(job, None)` or `(None, redirect)`.

    A missing/blank/unknown `job_id` from a query string redirects to `/jobs`
    with a flash. With `optional=True`, a blank `job_id` is allowed and yields
    `(None, None)` — used by routes that also work résumé-only (interview).
    """
    if not job_id:
        return (None, None) if optional else (None, _list_redirect("/jobs?msg=job_not_found"))
    job = db.get(JobPosting, job_id)
    if job is None:
        return None, _list_redirect("/jobs?msg=job_not_found")
    return job, None


def load_resume(db: Session, resume_id: int, *, optional: bool = False):
    """Return `(resume, None)` or `(None, redirect)` — see `load_job`."""
    if not resume_id:
        return (None, None) if optional else (None, _list_redirect("/resumes?msg=resume_not_found"))
    resume = db.get(Resume, resume_id)
    if resume is None:
        return None, _list_redirect("/resumes?msg=resume_not_found")
    return resume, None


def load_resume_and_job(db: Session, resume_id: int, job_id: int, *, job_optional: bool = False):
    """Shared guard for the coach / tailor / interview routes.

    Returns `(resume, job, None)` or `(None, None, redirect)`. `job_optional`
    lets `interview` run with no job (résumé-only mode) while `coach`/`tailor`
    require one — previously these disagreed on how a blank `job_id` was
    handled and `interview` couldn't reuse the helper.
    """
    resume, redirect = load_resume(db, resume_id)
    if redirect:
        return None, None, redirect
    job, redirect = load_job(db, job_id, optional=job_optional)
    if redirect:
        return None, None, redirect
    return resume, job, None


def normalize_job_status(value: str) -> str | None:
    """Form/query status value → canonical code.

    `""` (unchanged / not supplied) passes through as `""`; a non-empty value
    that isn't a known code or legacy label returns `None` so the caller can
    reject it consistently (422 for forms, 303+flash for quick actions).
    """
    if not value:
        return ""
    return JOB_STATUS.normalize(value)
