"""서비스 계층 공용 텍스트 유틸.

여러 서비스 모듈이 각자 조금씩 다르게 복제하던 작은 헬퍼(불릿 프리픽스 정규식,
길이 제한 잘라내기, 순서 보존 dedupe, 정량 표현 정규식, "기타" 카테고리 상수)를
한 곳으로 모은다. 서비스 간에는 public 심볼만 임포트하는 컨벤션을 따른다.

- `BULLET_PREFIX` — `resume_sections` / `interview_prep` / `text_formatter` 가 쓰던
  세 정규식의 상위집합. 문자 클래스는 동일했고 `^\\s*` 유무만 달랐는데, 세 호출부
  모두 이미 strip 된 라인에 쓰거나 선행 공백을 허용해도 무방해 하나로 합쳤다.
- `strip_bullet` — 라인에서 불릿 프리픽스를 한 번 제거.
- `truncate` — `interview_prep._truncate` / `profile_exporter._clip` /
  `resume_sections.first_line_label` 내부 로직의 통일. 셋 다 동일한
  `text[: limit - 1].rstrip() + "…"` 였다.
- `dedupe` — 순서 보존 중복 제거.
- `QUANT_PATTERN` — `resume_reviewer._QUANT_PATTERN` == `interview_prep._QUANT`.
- `UNKNOWN_CATEGORY` — `job_fit_coach` / `interview_prep` 의 `"기타"` 매직 문자열.
  (`enums.POSITION` 의 "기타/other" 와는 의미가 다르므로 별도로 둔다.)
- `strip_edge_decoration` — 라인 양끝 불릿/구분 기호·콜론·공백 제거. `resume_reviewer`
  / `profile_exporter` 의 `.strip(" \\t-•·*—")` 와 `resume_sections` / `interview_prep`
  의 `.strip(" \\t·-–—:：")` 로 갈라져 있던 세 문자셋의 상위집합.
"""

import re

BULLET_PREFIX = re.compile(r"^\s*(?:[-*•·▪‣◦▶○]|\d+[.)])\s+")

# 라인 양끝에서만 떼는 장식 문자 — 불릿, 대시(-, 엔/엠 대시), 별표, 가운뎃점,
# 그리고 소제목 끝의 콜론(:, ：). 내용 중간의 같은 문자는 건드리지 않는다.
_EDGE_DECORATION = " \t-*•·–—:："

QUANT_PATTERN = re.compile(r"\d+(\.\d+)?\s*(%|퍼센트|배|건|명|시간|일|개월|년|원|억|만)")

UNKNOWN_CATEGORY = "기타"


def strip_bullet(line: str) -> str:
    """라인 앞의 불릿/번호 프리픽스를 한 번 제거한다 (앞뒤 공백도 정리)."""
    return BULLET_PREFIX.sub("", line.strip(), count=1)


def truncate(text: str, limit: int = 60, ellipsis: str = "…") -> str:
    """`text` 를 `limit` 자로 자르고 넘치면 말줄임표를 붙인다."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + ellipsis


def dedupe(items: list[str]) -> list[str]:
    """순서를 보존하면서 중복을 제거한다."""
    return list(dict.fromkeys(items))


def strip_edge_decoration(line: str) -> str:
    """라인 양끝의 불릿/구분 기호·콜론·공백을 제거한다 (내용 중간은 그대로)."""
    return line.strip(_EDGE_DECORATION)
