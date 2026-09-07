"""공고별 지원 이벤트 로그 헬퍼.

`ApplicationEvent` 는 상태 스냅샷(JobPosting.status)만으로는 볼 수 없는 타임라인
— 상태 전이 이력과 면접 일정 — 을 남긴다. 순수 DB 헬퍼, 외부 호출 없음.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from app.enums import JOB_STATUS
from app.models import ApplicationEvent


def events_for_job(db, job_id: int) -> list[ApplicationEvent]:
    return list(
        db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.job_id == job_id)
            .order_by(ApplicationEvent.created_at, ApplicationEvent.id)
        )
    )


def record_status_change(db, job, new_code: str) -> ApplicationEvent | None:
    """job.status 가 실제로 바뀔 때만 "status" 이벤트를 남긴다. 호출부가 commit."""
    old_code = job.status or ""
    if new_code == old_code:
        return None
    event = ApplicationEvent(
        job_id=job.id, kind="status", from_status=old_code, to_status=new_code
    )
    db.add(event)
    return event


def add_interview_event(db, job_id: int, event_at: str, detail: str) -> ApplicationEvent:
    event = ApplicationEvent(
        job_id=job_id, kind="interview", event_at=event_at, detail=detail
    )
    db.add(event)
    return event


def delete_events_for_job(db, job_id: int) -> None:
    """공고 삭제 시 정리 — 무결성 강제가 아니라 뒷정리용."""
    for event in events_for_job(db, job_id):
        db.delete(event)


@dataclass
class TimelineEntry:
    kind: str
    label: str
    detail: str
    at: str  # 표시용 날짜 문자열 (created_at 날짜 또는 event_at)


def timeline(events: list[ApplicationEvent]) -> list[TimelineEntry]:
    """이벤트 목록을 사람이 읽는 타임라인 항목으로."""
    out: list[TimelineEntry] = []
    for event in events:
        stamp = event.created_at.date().isoformat() if event.created_at else ""
        if event.kind == "status":
            frm = JOB_STATUS.label_of(event.from_status) if event.from_status else "(없음)"
            to = JOB_STATUS.label_of(event.to_status)
            out.append(TimelineEntry("status", f"{frm} → {to}", "", stamp))
        elif event.kind == "interview":
            out.append(TimelineEntry("interview", "면접 일정", event.detail, event.event_at or stamp))
        else:
            out.append(TimelineEntry("note", "메모", event.detail, stamp))
    return out


def upcoming_interviews(events: list[ApplicationEvent], today: date) -> list[ApplicationEvent]:
    """오늘 이후(포함) 날짜가 잡힌 면접 이벤트, 가까운 순."""
    def _parsed(value: str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    dated = [(e, _parsed(e.event_at)) for e in events if e.kind == "interview"]
    return [e for e, d in sorted(
        (pair for pair in dated if pair[1] is not None and pair[1] >= today),
        key=lambda pair: pair[1],
    )]
