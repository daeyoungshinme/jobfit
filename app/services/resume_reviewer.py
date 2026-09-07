import re

from app.constants import RESUME_MIN_ACTION_VERB_HITS, RESUME_MIN_LENGTH, RESUME_MIN_QUANT_HITS
from app.schemas import CoachingSuggestion
from app.services.text_utils import QUANT_PATTERN

_SECTION_PATTERNS = {
    "경력/경험": re.compile(r"경력|경험|근무|재직"),
    "프로젝트": re.compile(r"프로젝트|project", re.IGNORECASE),
    "학력": re.compile(r"학력|대학교|대학|졸업"),
    "기술/스킬": re.compile(r"기술\s*스택|스킬|skill", re.IGNORECASE),
}

_IMPROVEMENT_WORD_PATTERN = re.compile(r"증가|감소|향상|절감|단축|달성|개선")
_ACTION_VERBS = ["개발", "설계", "구축", "운영", "리드", "주도", "담당", "최적화", "도입", "분석", "기획", "해결"]


def extract_achievement_lines(raw_text: str, limit: int = 6) -> list[str]:
    """이력서 원문에서 성과로 읽히는 줄(정량 수치 또는 액션 동사)을 점수 높은 순으로 추린다.

    app.services.profile_exporter 가 플랫폼 프로필 문구를 만들 때 공유한다. review_resume 와
    같은 판정 상수(text_utils.QUANT_PATTERN / _IMPROVEMENT_WORD_PATTERN / _ACTION_VERBS)를 재사용한다.
    """
    scored: list[tuple[int, int, str]] = []
    for idx, line in enumerate((raw_text or "").splitlines()):
        text = line.strip(" \t-•·*—")
        if len(text) < 8 or (text.startswith("[") and text.endswith("]")):
            continue
        score = (
            len(QUANT_PATTERN.findall(text)) * 2
            + len(_IMPROVEMENT_WORD_PATTERN.findall(text))
            + sum(1 for verb in _ACTION_VERBS if verb in text)
        )
        if score:
            scored.append((score, idx, text))
    scored.sort(key=lambda t: (-t[0], t[1]))  # 점수 내림차순, 동점은 원문 순서
    return [text for _score, _idx, text in scored[:limit]]


def review_resume(raw_text: str, extracted_skill_count: int) -> list[CoachingSuggestion]:
    """Produce rule-based improvement suggestions for a resume."""
    suggestions: list[CoachingSuggestion] = []
    text = raw_text or ""

    if len(text.strip()) < RESUME_MIN_LENGTH:
        suggestions.append(CoachingSuggestion(
            status="warning",
            title="이력서 분량이 짧습니다",
            detail=f"현재 약 {len(text.strip())}자입니다. 경력/프로젝트별 구체적인 역할과 성과를 더 추가하는 것을 권장합니다.",
        ))
    else:
        suggestions.append(CoachingSuggestion(
            status="ok",
            title="이력서 분량은 충분합니다",
            detail=f"현재 약 {len(text.strip())}자로, 세부 내용을 담기에 적절한 분량입니다.",
        ))

    for section_name, pattern in _SECTION_PATTERNS.items():
        if pattern.search(text):
            suggestions.append(CoachingSuggestion(
                status="ok",
                title=f"'{section_name}' 섹션이 확인됩니다",
                detail="해당 항목이 이력서에 포함되어 있습니다.",
            ))
        else:
            suggestions.append(CoachingSuggestion(
                status="warning",
                title=f"'{section_name}' 섹션이 보이지 않습니다",
                detail="채용담당자가 빠르게 파악할 수 있도록 해당 섹션을 명시적으로 추가하는 것을 권장합니다.",
            ))

    quant_hits = len(QUANT_PATTERN.findall(text)) + len(_IMPROVEMENT_WORD_PATTERN.findall(text))
    if quant_hits >= RESUME_MIN_QUANT_HITS:
        suggestions.append(CoachingSuggestion(
            status="ok",
            title="정량적 성과 표현이 포함되어 있습니다",
            detail=f"수치/개선 표현이 {quant_hits}건 발견되었습니다. 채용담당자에게 성과를 구체적으로 어필할 수 있습니다.",
        ))
    else:
        suggestions.append(CoachingSuggestion(
            status="warning",
            title="정량적 성과 표현이 부족합니다",
            detail="'처리 시간 30% 단축', '트래픽 20% 증가' 처럼 숫자로 표현된 성과를 추가하면 설득력이 높아집니다.",
        ))

    action_hits = sum(1 for verb in _ACTION_VERBS if verb in text)
    if action_hits >= RESUME_MIN_ACTION_VERB_HITS:
        suggestions.append(CoachingSuggestion(
            status="ok",
            title="주도적인 표현(액션 동사)이 충분합니다",
            detail=f"'개발/설계/구축/리드' 등 주도적 표현이 {action_hits}종 발견되었습니다.",
        ))
    else:
        suggestions.append(CoachingSuggestion(
            status="warning",
            title="주도적인 표현(액션 동사)이 부족합니다",
            detail="'담당했다' 보다 '설계했다', '주도했다', '개선했다' 처럼 본인의 역할이 드러나는 동사를 사용해 보세요.",
        ))

    if extracted_skill_count == 0:
        suggestions.append(CoachingSuggestion(
            status="warning",
            title="인식된 기술 스킬이 없습니다",
            detail="기술 스택을 이력서에 명시적으로 나열하면 채용공고와의 매칭 정확도가 높아집니다.",
        ))
    else:
        suggestions.append(CoachingSuggestion(
            status="ok",
            title=f"기술 스킬 {extracted_skill_count}개가 인식되었습니다",
            detail="매칭 대시보드에서 채용공고 요구 스킬과 비교할 수 있습니다.",
        ))

    suggestions.sort(key=lambda s: s.status != "warning")
    return suggestions
