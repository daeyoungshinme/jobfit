"""경력 조건 문자열 파싱 — 공용 단일 소스.

"3~5년"·"5년 이상" 같은 자유 입력과 `EXPERIENCE_LEVEL` enum 코드/라벨을 경계
(min/max) 또는 버킷("신입"/"경력")으로 해석한다. 이전에는 `matcher`(경력 적합도
축), `interview_prep`(행동 질문 버킷), `job_parser`(공고 파싱)가 각자 조금씩 다른
정규식으로 같은 문자열을 재파싱했다.
"""

import re

from app.enums import EXPERIENCE_LEVEL

# "3~5년"·"3-5년" 모두 허용 — job_parser 가 붙여넣은 공고 텍스트에서 하이픈 표기도
# 받는다. \b 로 "2020~2023년"(설립연도) 같은 4자리와 앞 토큰 붙은 경우를 배제하되
# 1~2자리로 상한을 둔다.
EXPERIENCE_RANGE_RE = re.compile(r"\b(\d{1,2})\s*[~\-]\s*(\d{1,2})\s*년")
# "5년 이상"·"5년~"·"5년+"
EXPERIENCE_MIN_RE = re.compile(r"(\d{1,2})\s*년\s*(?:이상|~|\+)")

_LEADING_NUMBER_RE = re.compile(r"\s*(\d+)")


def parse_experience_bounds(job_experience: str) -> tuple[int, int | None] | None:
    """공고 경력 조건 → (min_years, max_years|None). 축이 적용되지 않으면 None
    ('무관'·미상·자유 텍스트). 표준 버킷 코드/라벨을 먼저 보고, 아니면
    '3~5년'·'5년 이상' 같은 자유 입력 문자열을 정규식으로 해석한다."""
    if not job_experience:
        return None
    member = EXPERIENCE_LEVEL.get(EXPERIENCE_LEVEL.normalize(job_experience))
    if member is not None:
        if member.meta.get("bucket") is None:  # "무관"
            return None
        return member.meta.get("min_years", 0), member.meta.get("max_years")
    range_match = EXPERIENCE_RANGE_RE.search(job_experience)
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        return (lo, hi) if lo <= hi else (hi, lo)
    min_match = EXPERIENCE_MIN_RE.search(job_experience)
    if min_match:
        return int(min_match.group(1)), None
    return None


def describe_bounds(lo: int, hi: int | None) -> str:
    """(lo, hi) 경계를 사람이 읽는 문자열로 ("3~5년" / "5년 이상" / "신입")."""
    if hi is None:
        return f"{lo}년 이상"
    if lo == hi:
        return "신입" if lo == 0 else f"{lo}년"
    return f"{lo}~{hi}년"


def experience_bucket(experience_level: str) -> str | None:
    """경력 코드 또는 자유 입력 범위("2~8년") → 행동 질문 버킷("신입"/"경력"/None)."""
    member = EXPERIENCE_LEVEL.get(EXPERIENCE_LEVEL.normalize(experience_level))
    if member is not None:
        return member.meta.get("bucket")
    lead = _LEADING_NUMBER_RE.match(experience_level or "")
    if lead:
        return "신입" if int(lead.group(1)) == 0 else "경력"
    return None
