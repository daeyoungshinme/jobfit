from datetime import date

from app.templates import deadline_dday

_TODAY = date(2026, 9, 7)


def test_deadline_dday_none_for_missing_or_unparseable():
    assert deadline_dday("", today=_TODAY) is None
    assert deadline_dday(None, today=_TODAY) is None
    assert deadline_dday("나중에", today=_TODAY) is None  # 해석 불가


def test_deadline_dday_always_hiring_returns_badge():
    always = deadline_dday("상시", today=_TODAY)
    assert always["badge"] == "상시 채용"
    assert always["urgent"] is False
    assert always["days"] is None


def test_deadline_dday_urgent_within_a_week():
    soon = deadline_dday("2026-09-10", today=_TODAY)
    assert soon["urgent"] is True
    assert soon["badge"] == "마감 D-3"
    assert soon["css"] == "tag-required"

    today_due = deadline_dday("2026-09-07", today=_TODAY)
    assert today_due["urgent"] is True
    assert today_due["badge"] == "오늘 마감"


def test_deadline_dday_far_shows_plain_date_not_urgent():
    far = deadline_dday("2026-12-01", today=_TODAY)
    assert far["urgent"] is False
    assert far["badge"] == "마감 2026-12-01"
    assert far["css"] == "tag-source"


def test_deadline_dday_past():
    past = deadline_dday("2026-05-01", today=_TODAY)
    assert past["urgent"] is False
    assert past["badge"] == "마감 지남"
    assert past["days"] < 0
