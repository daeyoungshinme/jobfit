"""이력서를 외부 플랫폼(LinkedIn / 리멤버 / 원티드·잡코리아) 프로필 양식에 맞는
복사용 텍스트로 변환한다.

전부 규칙 기반 문자열 조립 — 외부 AI/서비스 호출 없음. 스킬 인식·카테고리 분류는
skill_extractor, 성과 문장 추출은 resume_reviewer.extract_achievement_lines 를 재사용한다.

자동 게시(업로드)는 지원하지 않는다. LinkedIn·리멤버는 프로필 쓰기 API가 없고, 그런
연동은 JobFit 의 "외부 서비스 호출 없음" 원칙에도 맞지 않는다. 생성된 문구를 사용자가
복사해 각 플랫폼에 직접 붙여넣는 흐름이다.
"""

import re
from dataclasses import dataclass, field

from app.constants import POSITIONS
from app.services.resume_reviewer import extract_achievement_lines
from app.services.skill_extractor import skill_category_map

_YEARS_PATTERN = re.compile(r"(\d{1,2})\s*년(?!제)")  # "3년차" O, "3년제 대학" X
_MAX_YEARS = 40

# role 추측용 보조 키워드 — POSITIONS 정식 명칭에 안 걸릴 때 이력서 본문에서 찾는다.
_ROLE_KEYWORDS = [
    "백엔드", "프론트엔드", "풀스택", "데이터 엔지니어", "데이터 사이언티스트",
    "DevOps", "인프라", "안드로이드", "iOS", "머신러닝", "ML", "QA",
]

_LOW_SIGNAL_WARNING = (
    "이 이력서는 구조화된 항목이 없어 자동 생성 품질이 낮습니다. "
    "폼(직접 입력)으로 다시 등록하거나 아래 문구를 직접 다듬어 사용하세요."
)


@dataclass
class ProfileSection:
    label: str
    body: str
    hint: str = ""


@dataclass
class PlatformProfile:
    platform: str
    key: str  # DOM id 접두 ("linkedin" / "remember" / "wanted_jobkorea")
    sections: list[ProfileSection]
    note: str = ""


@dataclass
class ProfileBundle:
    profiles: list[PlatformProfile] = field(default_factory=list)
    warning: str = ""


@dataclass
class _ResumeFacts:
    label: str
    skills: list[str]
    ordered_skills: list[str]
    career_text: str
    projects_text: str
    education_text: str
    achievements: list[str]
    role: str
    years: int | None
    categories: list[str]
    is_form: bool


# --- 소스 데이터 정규화 ---------------------------------------------------------


def _order_by_demand(skills: list[str], demand: list[str] | None) -> list[str]:
    """시장 수요(demand) 순으로 스킬을 정렬하고, 수요 목록에 없는 스킬은 알파벳순으로 뒤에 붙인다."""
    skill_set = set(skills)
    ordered = [name for name in (demand or []) if name in skill_set]
    seen = set(ordered)
    ordered.extend(sorted(name for name in skills if name not in seen))
    return ordered


def _guess_role(career_text: str, raw_text: str) -> str:
    haystack = f"{career_text}\n{raw_text}"
    for position in POSITIONS:
        if position == "기타":
            continue
        if position in haystack:
            return position
    for keyword in _ROLE_KEYWORDS:
        if keyword in haystack:
            return keyword
    return ""


def _guess_years(text: str) -> int | None:
    values = [int(m) for m in _YEARS_PATTERN.findall(text)]
    values = [v for v in values if 0 < v <= _MAX_YEARS]
    return max(values) if values else None


def _first_nonempty_line(text: str) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip(" \t-•·*—")
        if stripped:
            return stripped
    return ""


def _clip(text: str, max_len: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def _build_facts(resume, skill_demand: list[str] | None) -> _ResumeFacts:
    structured = resume.structured or {}
    is_form = resume.source_type == "form"
    career_text = structured.get("career", "") if is_form else ""
    projects_text = structured.get("projects", "") if is_form else ""
    education_text = structured.get("education", "") if is_form else ""

    skills = list(resume.extracted_skills or [])
    ordered_skills = _order_by_demand(skills, skill_demand)
    raw_text = resume.raw_text or ""
    category_map = skill_category_map()
    categories = list(
        dict.fromkeys(c for c in (category_map.get(s) for s in ordered_skills) if c)
    )

    return _ResumeFacts(
        label=resume.label,
        skills=skills,
        ordered_skills=ordered_skills,
        career_text=career_text,
        projects_text=projects_text,
        education_text=education_text,
        achievements=extract_achievement_lines(raw_text),
        role=_guess_role(career_text, raw_text),
        years=_guess_years(f"{career_text}\n{raw_text}"),
        categories=categories,
        is_form=is_form,
    )


# --- 생성 프리미티브 ----------------------------------------------------------


def _headline(facts: _ResumeFacts, max_len: int) -> str:
    parts = [facts.role or "개발자", *facts.ordered_skills[:3]]
    prefix = f"{facts.years}년차 " if facts.years else ""
    while parts:
        head = prefix + " · ".join(parts)
        if len(head) <= max_len:
            return head
        parts.pop()
    return _clip(prefix + (facts.role or "개발자"), max_len)


def _summary_paragraph(facts: _ResumeFacts, *, sentences: int) -> str:
    candidates: list[str] = []

    if facts.years and facts.role:
        candidates.append(f"{facts.years}년차 {facts.role}입니다.")
    elif facts.role:
        candidates.append(f"{facts.role}입니다.")
    else:
        candidates.append(f"'{facts.label}' 이력서를 바탕으로 작성한 프로필입니다.")

    if facts.ordered_skills:
        candidates.append(f"주요 기술은 {', '.join(facts.ordered_skills[:6])}입니다.")

    if facts.achievements:
        candidates.append(f"대표 성과로는 {_clip(facts.achievements[0], 60)} 등이 있습니다.")

    career_line = _first_nonempty_line(facts.career_text)
    if career_line:
        line = _clip(career_line, 80)
        candidates.append(line if line.endswith((".", "다", "요", "…")) else line + ".")

    return " ".join(candidates[:sentences])


def _experience_bullets(facts: _ResumeFacts, cap: int) -> list[str]:
    bullets = [f"- {line}" for line in facts.achievements]

    if len(bullets) < 3 and facts.career_text:
        for line in facts.career_text.splitlines():
            stripped = line.strip(" \t-•·*—")
            entry = f"- {stripped}"
            if stripped and entry not in bullets:
                bullets.append(entry)

    if not bullets:
        return ["- 이력서 원문에서 담당 업무와 성과를 정리해 붙여넣으세요."]
    return bullets[:cap]


def _skill_list(facts: _ResumeFacts, max_count: int) -> str:
    return ", ".join(facts.ordered_skills[:max_count])


def _keywords(facts: _ResumeFacts, n: int) -> str:
    parts = [facts.role, *facts.ordered_skills[:n], *facts.categories[:3]]
    return ", ".join(dict.fromkeys(p for p in parts if p))


# --- 플랫폼별 조립 ----------------------------------------------------------


def _linkedin_profile(facts: _ResumeFacts) -> PlatformProfile:
    bullets = _experience_bullets(facts, 8)
    auto_extracted = bool(facts.achievements)
    open_to_work = (
        (f"희망 직무: {facts.role}\n" if facts.role else "")
        + "프로필 사진에 #OpenToWork 배지를 켜고 희망 직무·근무형태·지역을 설정하세요. "
        "채용담당자에게만 표시하는 옵션도 있습니다."
    )
    return PlatformProfile(
        platform="LinkedIn",
        key="linkedin",
        note="LinkedIn > 프로필 편집에서 각 항목에 붙여넣으세요. 자동 게시는 지원하지 않습니다.",
        sections=[
            ProfileSection(
                "헤드라인", _headline(facts, 120),
                "프로필 상단 한 줄. 검색 노출에 영향을 줍니다.",
            ),
            ProfileSection(
                "소개 (About)", _summary_paragraph(facts, sentences=4),
                "최대 2,600자. 뒤에 핵심 성과를 이어 붙여도 좋습니다.",
            ),
            ProfileSection(
                "경력 설명 (요점)", "\n".join(bullets),
                "각 회사 경력 항목의 '설명'란에 회사별로 나눠 붙여넣으세요."
                + ("" if auto_extracted else " (자동 추출된 성과 문장이 없습니다.)"),
            ),
            ProfileSection(
                "스킬", _skill_list(facts, 50),
                "LinkedIn은 스킬을 최대 50개까지 등록할 수 있습니다. 시장 수요가 높은 순으로 정렬했습니다.",
            ),
            ProfileSection(
                "Open to work 안내", open_to_work,
                "JobFit은 구직 상태를 대신 설정하지 못합니다. LinkedIn에서 직접 켜세요.",
            ),
        ],
    )


def _remember_profile(facts: _ResumeFacts) -> PlatformProfile:
    return PlatformProfile(
        platform="리멤버",
        key="remember",
        note="리멤버 앱 > 내 프로필에서 편집. 명함 기반이라 경력 요약은 짧을수록 좋습니다.",
        sections=[
            ProfileSection(
                "한 줄 소개", _headline(facts, 50),
                "프로필 상단, 이름 아래 표시됩니다.",
            ),
            ProfileSection(
                "경력 요약", _summary_paragraph(facts, sentences=2),
                "3~4문장 이내로 유지하세요.",
            ),
            ProfileSection(
                "전문 분야 / 키워드", _keywords(facts, 8),
                "리멤버 커리어 > 전문 분야 태그에 입력. 헤드헌터 검색에 사용됩니다.",
            ),
        ],
    )


def _wanted_jobkorea_profile(facts: _ResumeFacts) -> PlatformProfile:
    return PlatformProfile(
        platform="원티드 · 잡코리아",
        key="wanted_jobkorea",
        note="원티드/잡코리아 이력서의 '자기소개'와 '보유 스킬' 항목에 붙여넣으세요.",
        sections=[
            ProfileSection(
                "자기소개", _summary_paragraph(facts, sentences=3),
                "이력서 상단 자기소개란. 3~5문장 권장.",
            ),
            ProfileSection(
                "핵심 경험", "\n".join(_experience_bullets(facts, 5)),
                "경력기술서 요약으로 활용하세요.",
            ),
            ProfileSection(
                "보유 스킬", _skill_list(facts, 30),
                "쉼표로 구분. 잡코리아는 스킬 태그, 원티드는 자유 입력.",
            ),
        ],
    )


def build_platform_profiles(resume, *, skill_demand: list[str] | None = None) -> ProfileBundle:
    """이력서 하나로 세 플랫폼(LinkedIn / 리멤버 / 원티드·잡코리아)용 프로필 문구를 만든다.

    skill_demand 는 시장 수요 순으로 정렬된 스킬명 리스트(라우터가
    matcher.skill_ranking 결과를 넘긴다). 서비스 자체는 DB 에 의존하지 않는다.
    """
    facts = _build_facts(resume, skill_demand)
    bundle = ProfileBundle(
        profiles=[
            _linkedin_profile(facts),
            _remember_profile(facts),
            _wanted_jobkorea_profile(facts),
        ]
    )
    if not facts.skills and not facts.career_text and not facts.achievements:
        bundle.warning = _LOW_SIGNAL_WARNING
    return bundle
