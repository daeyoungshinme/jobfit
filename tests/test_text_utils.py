import pytest

from app.services.text_utils import (
    BULLET_PREFIX,
    QUANT_PATTERN,
    UNKNOWN_CATEGORY,
    dedupe,
    strip_bullet,
    strip_edge_decoration,
    truncate,
)


@pytest.mark.parametrize(
    "line",
    [
        "- 항목",
        "* 항목",
        "• 항목",
        "· 항목",
        "▪ 항목",
        "‣ 항목",
        "◦ 항목",
        "▶ 항목",
        "○ 항목",
        "1. 항목",
        "2) 항목",
        "   - 선행 공백이 있는 항목",
    ],
)
def test_bullet_prefix_matches_known_bullets(line):
    assert BULLET_PREFIX.match(line)


@pytest.mark.parametrize("line", ["항목 - 중간 대시", "1.항목 (공백 없음)", "[대괄호] 항목"])
def test_bullet_prefix_ignores_non_bullets(line):
    assert BULLET_PREFIX.match(line) is None


def test_strip_bullet_removes_one_prefix():
    assert strip_bullet("- 결제 게이트웨이 구축") == "결제 게이트웨이 구축"
    assert strip_bullet("  * 로그 파이프라인 ") == "로그 파이프라인"
    assert strip_bullet("일반 문장") == "일반 문장"


@pytest.mark.parametrize(
    "line,expected",
    [
        ("  - 주요 성과 —", "주요 성과"),
        ("· 프로젝트 리드 :", "프로젝트 리드"),
        ("주요 성과: 매출 20% 증가", "주요 성과: 매출 20% 증가"),  # 중간 콜론은 유지
        ("＊＊ 강조 ＊＊", "＊＊ 강조 ＊＊"),  # 전각 별표는 장식 문자 아님
    ],
)
def test_strip_edge_decoration(line, expected):
    assert strip_edge_decoration(line) == expected


def test_truncate_boundary():
    assert truncate("12345", 5) == "12345"
    assert truncate("123456", 5) == "1234…"
    assert truncate("  padded  ", 20) == "padded"
    assert truncate(None) == ""
    assert truncate("abc def ghij", 8) == "abc def…"


def test_dedupe_preserves_order():
    assert dedupe(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert dedupe([]) == []


@pytest.mark.parametrize(
    "text",
    ["처리 시간 30% 단축", "트래픽 20 퍼센트 증가", "동시 접속 1.5배", "월 12건 처리", "5년 근무"],
)
def test_quant_pattern_hits(text):
    assert QUANT_PATTERN.search(text)


def test_quant_pattern_misses_plain_text():
    assert QUANT_PATTERN.search("성과를 냈습니다") is None


def test_unknown_category_constant():
    assert UNKNOWN_CATEGORY == "기타"
