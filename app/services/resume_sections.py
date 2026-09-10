"""이력서 원문 텍스트를 섹션·블록 단위로 잘라내는 공용 헬퍼.

`resume_reviewer` 는 섹션의 *존재 여부* 만 검사하지만, 면접 질문 생성처럼
"프로젝트 섹션의 각 항목" 이 필요한 곳에서는 본문을 실제로 잘라내야 한다.
form 이력서는 `resume.structured` 를 그대로 신뢰하고, file 이력서는 헤딩 라인을
스캔한다. 헤딩을 못 찾으면 빈 문자열을 돌려주고, 호출부는 관련 질문을 조용히
건너뛴다.
"""

import re

from app.services.text_utils import BULLET_PREFIX, strip_bullet, strip_edge_decoration, truncate

# 헤딩 라인은 (장식 제거 후) 키워드 + 흔한 접미어만으로 이뤄져야 한다 — fullmatch.
# 내용 문장이 키워드를 품고 있어도("OO대학교 컴퓨터공학 졸업") 헤딩으로 오인하지 않도록.
_HEADING_SUFFIX = r"(?:\s*(?:사항|경험|내용|요약|정보|목록))?"
_HEADING_KEYWORDS = [
    ("career", re.compile(rf"(?:경력|경력기술서|career|work\s*experience){_HEADING_SUFFIX}", re.IGNORECASE)),
    ("projects", re.compile(rf"(?:프로젝트|projects?|toy\s*projects?){_HEADING_SUFFIX}", re.IGNORECASE)),
    ("education", re.compile(rf"(?:학력|학위|education){_HEADING_SUFFIX}", re.IGNORECASE)),
    ("skills", re.compile(rf"(?:기술\s*스택|보유\s*기술|스킬|skills?|tech\s*stack){_HEADING_SUFFIX}", re.IGNORECASE)),
]

_LEAD_DECORATION = re.compile(r"^[\s\[\(【<#*■◆▶●○∙・]+")
_TRAIL_DECORATION = re.compile(r"[\s\]\)】>#*:：]+$")


def _clean_heading(line: str) -> str:
    stripped = _LEAD_DECORATION.sub("", line.strip())
    return _TRAIL_DECORATION.sub("", stripped).strip()


def _match_heading(line: str) -> str | None:
    if not line.strip() or BULLET_PREFIX.match(line):
        return None
    cleaned = _clean_heading(line)
    if not cleaned or len(cleaned) > 20:
        return None
    for key, pattern in _HEADING_KEYWORDS:
        if pattern.fullmatch(cleaned):
            return key
    return None


def split_resume_sections(raw_text: str) -> dict[str, str]:
    """자유 형식/합성 이력서 텍스트를 {career, projects, education, skills} 본문으로 분리."""
    result = {"career": "", "projects": "", "education": "", "skills": ""}
    if not raw_text:
        return result

    buckets: dict[str, list[str]] = {key: [] for key in result}
    current: str | None = None
    for line in raw_text.splitlines():
        key = _match_heading(line)
        if key is not None:
            current = key
            continue
        if current is not None:
            buckets[current].append(line)

    for key, lines in buckets.items():
        result[key] = "\n".join(lines).strip()
    return result


def sections_for_resume(resume) -> dict[str, str]:
    """form 이력서는 structured 를, file 이력서는 raw_text 스캔 결과를 돌려준다."""
    structured = resume.structured or {}
    if resume.source_type == "form" and structured:
        return {
            "career": structured.get("career", "") or "",
            "projects": structured.get("projects", "") or "",
            "education": structured.get("education", "") or "",
            "skills": structured.get("skills_text", "") or "",
        }
    return split_resume_sections(resume.raw_text or "")


# 섹션 키 → 이력서 리뷰(resume_reviewer)에 노출되는 한국어 이름.
SECTION_DISPLAY_NAMES = {
    "career": "경력/경험",
    "projects": "프로젝트",
    "education": "학력",
    "skills": "기술/스킬",
}


def detect_sections(resume) -> dict[str, bool]:
    """이력서에 각 섹션이 존재하는지 — 섹션 존재 판정의 단일 진실 소스.

    form 이력서는 structured 값을, file 이력서는 헤딩 스캔 결과를 신뢰한다.
    본문에 키워드가 스쳤다고("OO대학교 졸업") 섹션 있음으로 치지 않는다 —
    이전에 resume_reviewer 가 느슨한 re.search 로 오판하던 부분.
    """
    return {key: bool(text.strip()) for key, text in sections_for_resume(resume).items()}


def detect_sections_from_text(raw_text: str) -> dict[str, bool]:
    """Resume 객체 없이 raw_text 만으로 섹션 존재를 판정 (헤딩 스캔)."""
    return {key: bool(text.strip()) for key, text in split_resume_sections(raw_text).items()}


def split_blocks(section_text: str) -> list[str]:
    """섹션 본문을 개별 프로젝트/경력 항목으로 분리한다.

    빈 줄로 나뉜 덩어리를 우선하되, 한 덩어리가 전부 불릿 라인이면 불릿마다
    별도 항목으로 취급한다.
    """
    if not section_text or not section_text.strip():
        return []

    blocks: list[str] = []
    for chunk in re.split(r"\n\s*\n", section_text.strip()):
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        if len(lines) > 1 and all(BULLET_PREFIX.match(ln) for ln in lines):
            blocks.extend(strip_bullet(ln) for ln in lines)
        else:
            blocks.append(chunk.strip())
    return [block for block in blocks if block.strip()]


def first_line_label(block: str, limit: int = 60) -> str:
    """블록의 첫 비어있지 않은 줄을 라벨로 (불릿 제거 + 길이 제한)."""
    for line in block.splitlines():
        text = strip_edge_decoration(strip_bullet(line))
        if text:
            return truncate(text, limit)
    return ""
