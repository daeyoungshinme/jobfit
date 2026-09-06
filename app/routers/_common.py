"""Shared router helpers: the résumé-content form dependency and a get-or-404.

`ResumeContentForm` bundles the résumé content fields once instead of repeating
the same `Form(...)` params + `apply_resume_content` kwargs + error-render
`values` dict across `resumes.py` (create/edit) and `analysis.py` (tailor save).
Mirrors `jobs.py::JobForm`.
"""

from fastapi import Form, HTTPException
from sqlalchemy.orm import Session

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
