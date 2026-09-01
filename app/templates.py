from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.constants import (
    EMPTY_PREFERRED_SKILLS,
    EMPTY_REQUIRED_SKILLS,
    EMPTY_SKILLS,
    FEATURE_COACH,
    FEATURE_TAILOR,
    FLASH_MESSAGES,
    JOB_STATUS_DEFAULT,
    NO_SKILL_DATA,
    SELECT_JOB_PLACEHOLDER,
    SELECT_RESUME_PLACEHOLDER,
)
from app.services.text_formatter import render_bulleted_html

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def nav_active_for(path: str) -> str:
    if path.startswith("/resumes"):
        return "resumes"
    if path.startswith("/analysis"):
        return "analysis"
    return "jobs"


templates = Jinja2Templates(directory=_TEMPLATE_DIR)
templates.env.filters["bulleted"] = render_bulleted_html
templates.env.globals["flash_messages"] = FLASH_MESSAGES
templates.env.globals["nav_active_for"] = nav_active_for
templates.env.globals.update(
    JOB_STATUS_DEFAULT=JOB_STATUS_DEFAULT,
    EMPTY_SKILLS=EMPTY_SKILLS,
    EMPTY_REQUIRED_SKILLS=EMPTY_REQUIRED_SKILLS,
    EMPTY_PREFERRED_SKILLS=EMPTY_PREFERRED_SKILLS,
    NO_SKILL_DATA=NO_SKILL_DATA,
    SELECT_RESUME_PLACEHOLDER=SELECT_RESUME_PLACEHOLDER,
    SELECT_JOB_PLACEHOLDER=SELECT_JOB_PLACEHOLDER,
    FEATURE_TAILOR=FEATURE_TAILOR,
    FEATURE_COACH=FEATURE_COACH,
)
