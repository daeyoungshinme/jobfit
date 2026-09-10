"""도메인 enum — 코드값(ascii slug) + 한국어 라벨 + 메타데이터.

DB 에는 코드값을 저장하고 UI 에는 라벨을 노출한다. 서비스 로직은 라벨 문자열이
아니라 코드값·메타데이터로 분기한다 — 한국어 표시 문자열을 바꿔도 로직이 깨지지
않도록. 이전에는 `constants.JOB_STATUSES` 등의 라벨 리스트에 로직이 직접 결합돼
있어 `activity_report`·`interview_prep`·`job_parser`·`profile_exporter` 가 각자
라벨 집합을 재기입/재조립했다.

`normalize()` 는 코드값과 (구)라벨을 모두 받아 코드값으로 돌려준다 — DB 값
마이그레이션 전후, 그리고 조작된 POST 를 모두 안전하게 흡수한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EnumMember:
    code: str
    label: str
    aliases: tuple[str, ...] = ()  # 흡수할 과거 라벨/표기 변형
    meta: dict = field(default_factory=dict)


class EnumSet:
    def __init__(self, members: list[EnumMember]):
        self._members = tuple(members)
        self._by_code = {m.code: m for m in members}
        self._lookup: dict[str, str] = {}
        for m in members:
            for key in (m.code, m.label, *m.aliases):
                self._lookup[key] = m.code

    def __iter__(self):
        return iter(self._members)

    def __len__(self) -> int:
        return len(self._members)

    def codes(self) -> list[str]:
        return [m.code for m in self._members]

    def labels(self) -> list[str]:
        return [m.label for m in self._members]

    def choices(self) -> list[tuple[str, str]]:
        """`(code, label)` 쌍 — 템플릿 `<option value=code>label` 렌더용."""
        return [(m.code, m.label) for m in self._members]

    def get(self, code: str | None) -> EnumMember | None:
        return self._by_code.get(code or "")

    def has(self, code: str | None) -> bool:
        return (code or "") in self._by_code

    def label_of(self, code: str | None) -> str:
        member = self._by_code.get(code or "")
        return member.label if member else (code or "")

    def normalize(self, value: str | None) -> str | None:
        """코드값 또는 (구)라벨 → 코드값. 미상이면 None."""
        if not value:
            return None
        return self._lookup.get(value.strip())

    def codes_where(self, flag: str) -> set[str]:
        """`meta[flag]` 가 참인 멤버들의 코드값 집합."""
        return {m.code for m in self._members if m.meta.get(flag)}


JOB_STATUS = EnumSet([
    EnumMember("interest", "관심", meta={"early": True}),
    EnumMember("planned", "지원예정", meta={"early": True}),
    EnumMember("applied", "지원완료", meta={"applied": True, "awaiting": True}),
    EnumMember("doc_pass", "서류합격", meta={"applied": True, "advanced": True}),
    EnumMember("interview", "면접", meta={"applied": True, "advanced": True, "interviewing": True}),
    EnumMember("offer", "최종합격", meta={"applied": True, "advanced": True}),
    EnumMember("rejected", "불합격", meta={"applied": True, "advanced": True}),
    EnumMember("on_hold", "보류"),
])
JOB_STATUS_DEFAULT = "interest"


EXPERIENCE_LEVEL = EnumSet([
    EnumMember("entry", "신입", meta={"bucket": "신입", "min_years": 0, "max_years": 0}),
    EnumMember("y1_3", "1~3년", meta={"bucket": "경력", "min_years": 1, "max_years": 3}),
    EnumMember("y3_5", "3~5년", meta={"bucket": "경력", "min_years": 3, "max_years": 5}),
    EnumMember("y5_10", "5~10년", meta={"bucket": "경력", "min_years": 5, "max_years": 10}),
    EnumMember("y10p", "10년 이상", meta={"bucket": "경력", "min_years": 10, "max_years": None}),
    EnumMember("any", "무관", meta={"bucket": None}),
])


# terms: 제목·본문에서 직무를 추측할 때 찾는 키워드. 더 구체적인 라벨(풀스택)이
# 일반 라벨(백엔드/프론트엔드)보다 먼저 오도록 정렬돼 있다.
# adjacent: 직무 적합도(matcher.position_fit) 축에서 "완전히 다른 직무"보다는
# 가까운 것으로 볼 인접 직무 코드. matcher._positions_adjacent 가 양방향으로
# 확인하므로 한쪽에만 적어도 되지만, 가독성을 위해 양쪽에 대칭으로 둔다.
POSITION = EnumSet([
    EnumMember("fullstack", "풀스택 개발자", meta={"terms": ("풀스택",), "adjacent": ("backend", "frontend")}),
    EnumMember("android", "안드로이드 개발자", meta={"terms": ("안드로이드", "android"), "adjacent": ("ios",)}),
    EnumMember("ios", "iOS 개발자", meta={"terms": ("ios",), "adjacent": ("android",)}),
    EnumMember("data_eng", "데이터 엔지니어",
               meta={"terms": ("데이터 엔지니어", "데이터엔지니어", "data engineer", "dataengineer"),
                     "adjacent": ("data_sci", "devops")}),
    EnumMember("data_sci", "데이터 사이언티스트/AI・ML 엔지니어",
               meta={"terms": ("데이터 사이언티스트", "머신러닝", "인공지능", "ai 엔지니어", "ml 엔지니어"),
                     "adjacent": ("data_eng",)}),
    EnumMember("devops", "DevOps/인프라 엔지니어",
               meta={"terms": ("devops", "데브옵스", "인프라 엔지니어"), "adjacent": ("backend", "data_eng")}),
    EnumMember("qa", "QA 엔지니어", meta={"terms": ("qa", "품질관리", "품질보증")}),
    EnumMember("backend", "백엔드 개발자",
               meta={"terms": ("백엔드", "서버 개발자", "backend"), "adjacent": ("fullstack", "devops")}),
    EnumMember("frontend", "프론트엔드 개발자",
               meta={"terms": ("프론트엔드", "프론트 개발자", "frontend"), "adjacent": ("fullstack",)}),
    EnumMember("other", "기타", meta={"terms": ()}),
])


# 주소 부분매칭에 쓰이고 DB 에 코드로 저장되지 않으므로 코드=라벨(한글)을 유지한다.
# job_parser._SIDO_NAMES 정규식은 이 목록에서 생성한다.
REGION = EnumSet([
    EnumMember(name, name)
    for name in (
        "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
        "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
    )
])


# source_site_keys: 자유 입력 `source_site` 문자열(소문자)에 포함되면 이 채널을
# 지원 기록 폼의 기본 선택으로 추천한다.
APPLY_CHANNEL = EnumSet([
    EnumMember("saramin", "사람인", meta={"source_site_keys": ("사람인", "saramin")}),
    EnumMember("jobkorea", "잡코리아", meta={"source_site_keys": ("잡코리아", "jobkorea")}),
    EnumMember("wanted", "원티드", meta={"source_site_keys": ("원티드", "wanted")}),
    EnumMember("jobplanet", "잡플래닛", meta={"source_site_keys": ("잡플래닛", "jobplanet")}),
    EnumMember("linkedin", "LinkedIn", meta={"source_site_keys": ("linkedin", "링크드인")}),
    EnumMember("remember", "리멤버", meta={"source_site_keys": ("리멤버", "remember")}),
    EnumMember("programmers", "프로그래머스", meta={"source_site_keys": ("프로그래머스", "programmers")}),
    EnumMember("incruit", "인크루트", meta={"source_site_keys": ("인크루트", "incruit")}),
    EnumMember("rocketpunch", "로켓펀치", meta={"source_site_keys": ("로켓펀치", "rocketpunch")}),
    EnumMember("catch", "캐치", meta={"source_site_keys": ("캐치", "catch")}),
    EnumMember("company", "회사 채용페이지"),
    EnumMember("headhunter", "헤드헌터"),
    EnumMember("referral", "지인 추천"),
    EnumMember("other", "기타"),
])


# 공고 부가 정보(job_parser 추측 + 폼 수정). DB 에 코드 저장, UI 는 라벨.
EMPLOYMENT_TYPE = EnumSet([
    EnumMember("fulltime", "정규직"),
    EnumMember("contract", "계약직"),
    EnumMember("intern", "인턴"),
    EnumMember("dispatch", "파견"),
    EnumMember("freelance", "프리랜서"),
])

REMOTE_POLICY = EnumSet([
    EnumMember("office", "사무실 출근"),
    EnumMember("remote", "재택근무"),
    EnumMember("hybrid", "하이브리드"),
])


_ENUM_SETS = {
    "job_status": JOB_STATUS,
    "experience_level": EXPERIENCE_LEVEL,
    "position": POSITION,
    "region": REGION,
    "apply_channel": APPLY_CHANNEL,
    "employment_type": EMPLOYMENT_TYPE,
    "remote_policy": REMOTE_POLICY,
}


def enum_label(enum_name: str, code: str | None) -> str:
    """템플릿 전역 — 저장된 코드값을 한국어 라벨로. 미상 코드는 원문 그대로
    (경력 조건의 자유 입력 범위 "2~8년" 등)."""
    enum_set = _ENUM_SETS.get(enum_name)
    if enum_set is None:
        return code or ""
    return enum_set.label_of(code)
