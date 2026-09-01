"""Shared résumé-content write path.

Used by both the plain résumé edit form (`resumes.py`) and the job-tailored
editing workspace (`analysis.py::tailor`) so the two stay in lock-step on how
`raw_text` / `structured` are composed and how skills get re-extracted.
"""

from app.models import Resume
from app.services.skill_extractor import extract_skill_names


def compose_form_raw_text(career: str, projects: str, education: str, skills_text: str) -> str:
    return f"[경력]\n{career}\n\n[프로젝트]\n{projects}\n\n[학력]\n{education}\n\n[기술 스택]\n{skills_text}"


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
        resume.structured = {
            "career": career,
            "projects": projects,
            "education": education,
            "skills_text": skills_text,
        }
    resume.extracted_skills = extract_skill_names(resume.raw_text)
