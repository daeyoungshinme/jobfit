"""ISO 날짜(YYYY-MM-DD) 문자열 헬퍼 — 공용.

사용자 입력 날짜(지원일·면접일·마감일)는 다른 폼 필드처럼 문자열로 저장하므로
(`models.py` 참고), 폼 검증부는 형식을, 집계/표시부는 파싱을 각자 하던 것을 한
곳으로 모은다.
"""

import re
from datetime import date

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_iso_date(value: str) -> bool:
    """형식 검증 전용 — 'YYYY-MM-DD' 모양이면 True. 실제 유효한 날짜인지는
    보지 않는다(기존 폼 검증 동작 유지). 값을 쓸 때는 parse_iso_date 로 확인."""
    return bool(_ISO_DATE_RE.match(value or ""))


def parse_iso_date(value: str | None) -> date | None:
    """'YYYY-MM-DD' → date, 비었거나 문자열이 아니거나 해석 불가면 None."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None
