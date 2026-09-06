"""Shared résumé-content write path.

Used by both the plain résumé edit form (`resumes.py`) and the job-tailored
editing workspace (`analysis.py::tailor`) so the two stay in lock-step on how
`raw_text` / `structured` are composed, how skills get re-extracted, and which
fields are required before a write is allowed.
"""

from app.models import Resume
from app.services.skill_extractor import extract_skill_names
from app.services.validation import require_fields

_RAW_TEXT_REQUIRED_MESSAGE = {"raw_text": "이력서 원문을 입력해주세요."}
_FORM_CONTENT_REQUIRED_MESSAGE = "경력/프로젝트/학력/기술 스택 중 하나 이상은 입력해주세요."


def compose_form_raw_text(career: str, projects: str, education: str, skills_text: str) -> str:
    return f"[경력]\n{career}\n\n[프로젝트]\n{projects}\n\n[학력]\n{education}\n\n[기술 스택]\n{skills_text}"


def validate_resume_content(
    source_type: str,
    *,
    raw_text: str = "",
    career: str = "",
    projects: str = "",
    education: str = "",
    skills_text: str = "",
) -> dict[str, str]:
    """Field errors for a written résumé, keyed by field name.

    File-source résumés must keep a non-blank `raw_text`; form-source résumés
    must have at least one non-blank structured field so an all-blank submit
    can't overwrite stored content with the empty `compose_form_raw_text`
    skeleton. Shared by every résumé write path (`resumes.py::submit_resume_form`
    / `update_resume`, `analysis.py::save_tailored_resume`) so they reject the
    same empty input.
    """
    if source_type == "file":
        return require_fields({"raw_text": raw_text}, _RAW_TEXT_REQUIRED_MESSAGE)
    if not (career.strip() or projects.strip() or education.strip() or skills_text.strip()):
        return {"career": _FORM_CONTENT_REQUIRED_MESSAGE}
    return {}


def _form_structured(career: str, projects: str, education: str, skills_text: str) -> dict:
    return {
        "career": career,
        "projects": projects,
        "education": education,
        "skills_text": skills_text,
    }


def apply_resume_content(
    resume: Resume,
    *,
    raw_text: str = "",
    career: str = "",
    projects: str = "",
    education: str = "",
    skills_text: str = "",
) -> None:
    """Write edited content onto `resume` and re-extract its skills. Caller commits.

    File-source résumés edit `raw_text` directly; form-source résumés recompose
    it from the structured fields.
    """
    if resume.source_type == "file":
        resume.raw_text = raw_text
    else:
        resume.raw_text = compose_form_raw_text(career, projects, education, skills_text)
        resume.structured = _form_structured(career, projects, education, skills_text)
    resume.extracted_skills = extract_skill_names(resume.raw_text)


def new_resume(
    *,
    label: str,
    source_type: str,
    raw_text: str = "",
    career: str = "",
    projects: str = "",
    education: str = "",
    skills_text: str = "",
    structured: dict | None = None,
) -> Resume:
    """Build a new Resume, routing content through apply_resume_content().

    Keeps résumé *creation* (`resumes.py` upload / form) on the same raw_text /
    structured / skill-extraction rules as résumé *editing*.
    """
    resume = Resume(label=label, source_type=source_type, structured=structured or {})
    apply_resume_content(
        resume,
        raw_text=raw_text,
        career=career,
        projects=projects,
        education=education,
        skills_text=skills_text,
    )
    return resume
