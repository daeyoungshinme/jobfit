"""구직 활동 대시보드(/analysis/activity)용 집계.

채용공고(JobPosting)의 지원 상태 / 지원 경로(applied_via) / 지원일(applied_at) /
인바운드 여부(is_inbound)를 모아 상태별·채널별 현황과 후속 조치가 필요한 항목을 뽑는다.
외부 호출 없음 — 순수 파이썬 집계.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone

from app.enums import JOB_STATUS

STALE_AFTER_DAYS = 14
_ADVANCED = JOB_STATUS.codes_where("advanced")
_APPLIED = JOB_STATUS.codes_where("applied")
_EARLY_STAGE = JOB_STATUS.codes_where("early")
_AWAITING = JOB_STATUS.codes_where("awaiting")  # 지원완료(아직 미진행)
_INTERVIEWING = JOB_STATUS.codes_where("interviewing")


@dataclass
class ActivityRow:
    job_id: int
    title: str
    company: str
    status: str
    applied_via: str
    applied_at: str
    is_inbound: bool
    days_since_applied: int | None


@dataclass
class ActivityReport:
    total: int
    applied_count: int
    inbound_count: int
    status_counts: list[tuple[str, int]]
    channel_counts: list[tuple[str, int]]
    recent_applications: list[ActivityRow]
    awaiting_response: list[ActivityRow]
    inbound_leads: list[ActivityRow]
    interviewing: list[ActivityRow]


def _days_since(iso: str, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(iso)).days
    except ValueError:
        return None


def build_activity_report(jobs, today: date | None = None) -> ActivityReport:
    # applied_at 은 사용자 입력(로컬 날짜) 이지만 서버 기준일이 없으면 UTC 로 계산한다
    # — 자정 경계에서 최대 하루 오차. 정확도가 필요하면 라우터가 today 를 주입한다.
    today = today or datetime.now(timezone.utc).date()
    rows = [
        ActivityRow(
            job_id=job.id,
            title=job.title,
            company=job.company or "",
            status=JOB_STATUS.normalize(job.status) or (job.status or ""),
            applied_via=job.applied_via or "",
            applied_at=job.applied_at or "",
            is_inbound=bool(job.is_inbound),
            days_since_applied=_days_since(job.applied_at or "", today),
        )
        for job in jobs
    ]

    status_counts = [(s, sum(1 for r in rows if r.status == s)) for s in JOB_STATUS.codes()]
    channel_counts = Counter(r.applied_via for r in rows if r.applied_via).most_common()
    applied_count = sum(1 for r in rows if r.applied_at or r.status in _APPLIED)
    recent = sorted(
        (r for r in rows if r.applied_at), key=lambda r: r.applied_at, reverse=True
    )[:10]
    awaiting = [
        r
        for r in rows
        if r.status in _AWAITING
        and r.days_since_applied is not None
        and r.days_since_applied >= STALE_AFTER_DAYS
    ]
    inbound_leads = [r for r in rows if r.is_inbound and r.status in _EARLY_STAGE]
    interviewing = [r for r in rows if r.status in _INTERVIEWING]

    return ActivityReport(
        total=len(rows),
        applied_count=applied_count,
        inbound_count=sum(1 for r in rows if r.is_inbound),
        status_counts=status_counts,
        channel_counts=channel_counts,
        recent_applications=recent,
        awaiting_response=awaiting,
        inbound_leads=inbound_leads,
        interviewing=interviewing,
    )
