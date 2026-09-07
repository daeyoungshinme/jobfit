from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.constants import (
    EMPTY_CATEGORY_GAPS,
    EMPTY_PREFERRED_SKILLS,
    EMPTY_REQUIRED_SKILLS,
    EMPTY_SKILLS,
    FEATURE_COACH,
    FEATURE_COACH_SHORT,
    FEATURE_TAILOR,
    FEATURE_TAILOR_SHORT,
    FLASH_MESSAGES,
    NO_SKILL_DATA,
    NO_SKILL_DATA_REASON,
    SELECT_JOB_PLACEHOLDER,
    SELECT_PLACEHOLDER,
    SELECT_RESUME_PLACEHOLDER,
)
from app.enums import (
    APPLY_CHANNEL,
    EXPERIENCE_LEVEL,
    JOB_STATUS,
    JOB_STATUS_DEFAULT,
    POSITION,
    REGION,
    enum_label,
)
from app.services.text_formatter import render_bulleted_html

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def nav_active_for(path: str) -> str:
    if path.startswith("/resumes"):
        return "resumes"
    if path.startswith("/analysis/activity"):
        return "activity"
    if path.startswith("/analysis"):
        return "analysis"
    return "jobs"


templates = Jinja2Templates(directory=_TEMPLATE_DIR)
templates.env.filters["bulleted"] = render_bulleted_html
templates.env.globals["flash_messages"] = FLASH_MESSAGES
templates.env.globals["nav_active_for"] = nav_active_for
templates.env.globals["enum_label"] = enum_label
templates.env.globals.update(
    JOB_STATUS_DEFAULT=JOB_STATUS_DEFAULT,
    JOB_STATUS_CHOICES=JOB_STATUS.choices(),
    POSITION_CHOICES=POSITION.choices(),
    EXPERIENCE_LEVEL_CHOICES=EXPERIENCE_LEVEL.choices(),
    EXPERIENCE_LEVEL_CODES=EXPERIENCE_LEVEL.codes(),
    APPLY_CHANNEL_CHOICES=APPLY_CHANNEL.choices(),
    REGION_CHOICES=REGION.choices(),
    EMPTY_SKILLS=EMPTY_SKILLS,
    EMPTY_REQUIRED_SKILLS=EMPTY_REQUIRED_SKILLS,
    EMPTY_PREFERRED_SKILLS=EMPTY_PREFERRED_SKILLS,
    NO_SKILL_DATA=NO_SKILL_DATA,
    NO_SKILL_DATA_REASON=NO_SKILL_DATA_REASON,
    EMPTY_CATEGORY_GAPS=EMPTY_CATEGORY_GAPS,
    SELECT_PLACEHOLDER=SELECT_PLACEHOLDER,
    SELECT_RESUME_PLACEHOLDER=SELECT_RESUME_PLACEHOLDER,
    SELECT_JOB_PLACEHOLDER=SELECT_JOB_PLACEHOLDER,
    FEATURE_TAILOR=FEATURE_TAILOR,
    FEATURE_TAILOR_SHORT=FEATURE_TAILOR_SHORT,
    FEATURE_COACH=FEATURE_COACH,
    FEATURE_COACH_SHORT=FEATURE_COACH_SHORT,
)
