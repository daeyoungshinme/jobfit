from datetime import date

import pytest

from app.services.dates import is_iso_date, parse_iso_date


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-09-09", True),
        ("2026-13-45", True),   # 형식만 본다 (실제 유효성은 검사 안 함)
        ("2026-9-9", False),    # 한 자리 월/일은 거부
        ("2026/09/09", False),
        ("", False),
        ("상시", False),
        (None, False),
    ],
)
def test_is_iso_date(value, expected):
    assert is_iso_date(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-09-09", date(2026, 9, 9)),
        (" 2026-09-09 ", date(2026, 9, 9)),
        ("2026-13-45", None),   # 형식은 맞지만 날짜로 해석 불가
        ("", None),
        ("상시", None),
        (None, None),
        (20260909, None),       # 문자열 아님
    ],
)
def test_parse_iso_date(value, expected):
    assert parse_iso_date(value) == expected
