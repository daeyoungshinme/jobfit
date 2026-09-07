from datetime import date
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
    EMPLOYMENT_TYPE,
    EXPERIENCE_LEVEL,
    JOB_STATUS,
    JOB_STATUS_DEFAULT,
    POSITION,
    REGION,
    REMOTE_POLICY,
    enum_label,
)
from app.services.text_formatter import render_bulleted_html

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


_DEADLINE_URGENT_DAYS = 7


def deadline_dday(deadline: str | None, *, today: date | None = None) -> dict | None:
    """공고 마감일 문자열 → 목록/상세에서 쓸 뱃지 정보 dict, 아니면 None.

    None 이면 호출부가 마감 뱃지를 생략한다('상시'·빈값·해석 불가). `urgent`
    는 마감까지 7일 이하(오늘 포함)일 때 True — 목록에서 눈에 띄게 표시한다.
    """
    if not deadline or deadline.strip() in ("", "상시"):
        return None
    try:
        due = date.fromisoformat(deadline.strip())
    except ValueError:
        return None
    days = (due - (today or date.today())).days
    if days < 0:
        return {"badge": "마감 지남", "css": "tag", "urgent": False, "days": days}
    if days == 0:
        return {"badge": "오늘 마감", "css": "tag-required", "urgent": True, "days": 0}
    if days <= _DEADLINE_URGENT_DAYS:
        return {"badge": f"마감 D-{days}", "css": "tag-required", "urgent": True, "days": days}
    return {"badge": f"마감 {deadline}", "css": "tag-source", "urgent": False, "days": days}


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
templates.env.globals["deadline_dday"] = deadline_dday
templates.env.globals.update(
    JOB_STATUS_DEFAULT=JOB_STATUS_DEFAULT,
    JOB_STATUS_CHOICES=JOB_STATUS.choices(),
    POSITION_CHOICES=POSITION.choices(),
    EXPERIENCE_LEVEL_CHOICES=EXPERIENCE_LEVEL.choices(),
    EXPERIENCE_LEVEL_CODES=EXPERIENCE_LEVEL.codes(),
    APPLY_CHANNEL_CHOICES=APPLY_CHANNEL.choices(),
    REGION_CHOICES=REGION.choices(),
    EMPLOYMENT_TYPE_CHOICES=EMPLOYMENT_TYPE.choices(),
    REMOTE_POLICY_CHOICES=REMOTE_POLICY.choices(),
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
