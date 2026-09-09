import pytest

from app.services.experience import (
    describe_bounds,
    experience_bucket,
    parse_experience_bounds,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("entry", (0, 0)),
        ("y3_5", (3, 5)),
        ("y10p", (10, None)),
        ("신입", (0, 0)),          # (구)라벨 흡수
        ("3~5년", (3, 5)),         # 자유 입력 범위
        ("3-5년", (3, 5)),         # 하이픈 표기 (공고에서 붙여넣음)
        ("5년 이상", (5, None)),
        ("5년~", (5, None)),
        ("8~2년", (2, 8)),         # 뒤집힌 범위도 정렬
        ("any", None),            # '무관' → 축 제외
        ("무관", None),
        ("", None),
        ("협의", None),           # 해석 불가 자유 텍스트
    ],
)
def test_parse_experience_bounds(value, expected):
    assert parse_experience_bounds(value) == expected


@pytest.mark.parametrize(
    "lo,hi,expected",
    [
        (0, 0, "신입"),
        (3, 3, "3년"),
        (3, 5, "3~5년"),
        (5, None, "5년 이상"),
    ],
)
def test_describe_bounds(lo, hi, expected):
    assert describe_bounds(lo, hi) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("entry", "신입"),
        ("y5_10", "경력"),
        ("신입", "신입"),          # (구)라벨 흡수
        ("2~8년", "경력"),         # 자유 입력 범위
        ("0~1년", "신입"),
        ("any", None),
        ("", None),
    ],
)
def test_experience_bucket(value, expected):
    assert experience_bucket(value) == expected
