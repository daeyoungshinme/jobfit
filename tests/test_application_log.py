from app.models import ApplicationEvent
from app.services.application_log import (
    add_interview_event,
    delete_events_for_job,
    events_for_job,
    record_status_change,
    timeline,
)


def test_record_status_change_only_on_actual_change(db_session, job_factory):
    job = job_factory(status="interest")

    assert record_status_change(db_session, job, "interest") is None  # 변화 없음
    ev = record_status_change(db_session, job, "applied")
    db_session.commit()

    assert ev is not None
    events = events_for_job(db_session, job.id)
    assert len(events) == 1
    assert events[0].kind == "status"
    assert events[0].from_status == "interest"
    assert events[0].to_status == "applied"


def test_delete_events_for_job(db_session, job_factory):
    job = job_factory()
    add_interview_event(db_session, job.id, "2026-09-20", "1차")
    record_status_change(db_session, job, "applied")
    db_session.commit()
    assert events_for_job(db_session, job.id)

    delete_events_for_job(db_session, job.id)
    db_session.commit()
    assert events_for_job(db_session, job.id) == []


def test_timeline_renders_status_and_interview():
    events = [
        ApplicationEvent(job_id=1, kind="status", from_status="interest", to_status="applied"),
        ApplicationEvent(job_id=1, kind="interview", event_at="2026-09-20", detail="1차 기술"),
    ]
    entries = timeline(events)
    assert entries[0].label == "관심 → 지원완료"
    assert entries[1].kind == "interview" and entries[1].at == "2026-09-20"
    assert entries[1].detail == "1차 기술"
