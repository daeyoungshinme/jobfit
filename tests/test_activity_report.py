from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.enums import JOB_STATUS
from app.services.activity_report import build_activity_report

TODAY = date(2026, 9, 6)


def _job(**overrides):
    fields = {
        "id": 1,
        "title": "공고",
        "company": "회사",
        "status": "interest",
        "applied_via": "",
        "applied_at": "",
        "is_inbound": False,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _iso(days_ago):
    return (TODAY - timedelta(days=days_ago)).isoformat()


def test_status_counts_cover_every_status_in_order():
    report = build_activity_report([_job(status="interview")], today=TODAY)
    assert [s for s, _ in report.status_counts] == JOB_STATUS.codes()
    assert dict(report.status_counts)["interview"] == 1


def test_status_counts_accepts_legacy_korean_labels():
    # 마이그레이션 전 DB 값(한국어 라벨)도 코드로 정규화해 집계한다.
    report = build_activity_report([_job(status="면접")], today=TODAY)
    assert dict(report.status_counts)["interview"] == 1


def test_channel_counts_ranked_by_frequency():
    jobs = [
        _job(id=1, applied_via="wanted"),
        _job(id=2, applied_via="wanted"),
        _job(id=3, applied_via="linkedin"),
    ]
    report = build_activity_report(jobs, today=TODAY)
    assert report.channel_counts[0] == ("wanted", 2)


def test_awaiting_response_flags_stale_applied():
    stale = _job(id=1, status="applied", applied_at=_iso(20))
    fresh = _job(id=2, status="applied", applied_at=_iso(5))
    report = build_activity_report([stale, fresh], today=TODAY)
    assert [r.job_id for r in report.awaiting_response] == [1]


def test_awaiting_response_excludes_advanced_status():
    job = _job(status="doc_pass", applied_at=_iso(30))
    report = build_activity_report([job], today=TODAY)
    assert report.awaiting_response == []


def test_days_since_applied_handles_blank_and_garbage():
    jobs = [_job(id=1, applied_at=""), _job(id=2, applied_at="nope")]
    report = build_activity_report(jobs, today=TODAY)
    assert report.awaiting_response == []


def test_inbound_leads_only_early_stage():
    lead = _job(id=1, is_inbound=True, status="interest")
    interviewing = _job(id=2, is_inbound=True, status="interview")
    report = build_activity_report([lead, interviewing], today=TODAY)
    assert [r.job_id for r in report.inbound_leads] == [1]
    assert report.inbound_count == 2


def test_recent_applications_desc_and_capped_at_10():
    jobs = [_job(id=i, applied_at=_iso(i)) for i in range(1, 15)]
    report = build_activity_report(jobs, today=TODAY)
    assert len(report.recent_applications) == 10
    assert report.recent_applications[0].applied_at > report.recent_applications[-1].applied_at


def test_today_defaults_to_utc_date():
    utc_today = datetime.now(timezone.utc).date()
    stale = _job(id=1, status="applied", applied_at=(utc_today - timedelta(days=30)).isoformat())
    report = build_activity_report([stale])  # today 미주입
    assert [r.job_id for r in report.awaiting_response] == [1]


def test_applied_count_counts_status_or_date():
    jobs = [
        _job(id=1, status="applied"),                       # status 로 카운트
        _job(id=2, status="interest", applied_at=_iso(3)),  # 날짜로 카운트
        _job(id=3, status="interest"),                      # 미카운트
    ]
    report = build_activity_report(jobs, today=TODAY)
    assert report.applied_count == 2
