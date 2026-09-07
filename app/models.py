from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import JOB_STATUS_DEFAULT


def _now() -> datetime:
    # 네이티브 UTC. DateTime 컬럼이 tz-aware 값을 받으면 SQLite 가 tz 정보를
    # 버려서 저장/조회가 어긋나므로, 처음부터 tzinfo 를 떼고 UTC 기준으로 저장한다.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    source_site: Mapped[str] = mapped_column(String(100), default="")
    position: Mapped[str] = mapped_column(String(100))
    experience_level: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(20), default=JOB_STATUS_DEFAULT)
    raw_text: Mapped[str] = mapped_column(Text)
    main_tasks: Mapped[str] = mapped_column(Text, default="")
    required_text: Mapped[str] = mapped_column(Text, default="")
    preferred_text: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    # 원문에서 섹션 헤더(자격요건/우대사항 등)를 인식했는지. job_parser 가 저장하고
    # job_detail 이 "자동 인식 실패" 안내를 띄울지 판단하는 데 쓴다.
    sections_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    # 공고 부가 정보. employment_type/remote_policy 는 enum 코드, 나머지는 자유 텍스트
    # (deadline 은 ISO 'YYYY-MM-DD' 또는 "상시"). job_parser 가 추측하고 폼에서 수정 가능.
    employment_type: Mapped[str] = mapped_column(String(20), default="")
    remote_policy: Mapped[str] = mapped_column(String(20), default="")
    salary_text: Mapped[str] = mapped_column(String(200), default="")
    deadline: Mapped[str] = mapped_column(String(20), default="")
    benefits_text: Mapped[str] = mapped_column(Text, default="")
    process_text: Mapped[str] = mapped_column(Text, default="")
    # 지원 활동 추적. applied_at 은 사용자 입력값이라 다른 폼 필드처럼 문자열로 저장한다
    # (ISO 'YYYY-MM-DD'). applied_resume_id 는 의도적으로 FK 가 아니다 — 0 = 없음,
    # 참조된 이력서가 삭제돼도 템플릿이 안내 문구로 저하한다.
    applied_via: Mapped[str] = mapped_column(String(30), default="")
    applied_at: Mapped[str] = mapped_column(String(10), default="")
    applied_resume_id: Mapped[int] = mapped_column(Integer, default=0)
    memo: Mapped[str] = mapped_column(Text, default="")
    # 헤드헌터·리크루터가 먼저 제안한 공고(리멤버/LinkedIn 인바운드)면 True.
    is_inbound: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class ApplicationEvent(Base):
    """공고별 지원 이벤트 로그 (상태 전이 / 메모 / 면접 일정).

    `job_id` 는 의도적으로 FK 가 아니다 — 코드베이스 전체가 FK 를 쓰지 않고
    (JobPosting.applied_resume_id 와 같은 소프트 참조 패턴), 조회는 항상 job_id
    로 시작하므로 고아 이벤트도 무해하다. `index=True` 는 무결성이 아니라 조회
    성능용이다. 삭제 정리는 jobs.py::delete_job 이 수동으로 한다.
    """

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)  # 소프트 참조 (FK 아님)
    kind: Mapped[str] = mapped_column(String(20))  # "status" | "note" | "interview"
    from_status: Mapped[str] = mapped_column(String(20), default="")  # enum 코드
    to_status: Mapped[str] = mapped_column(String(20), default="")  # enum 코드
    # 사용자 입력 날짜(면접 일정 등)는 다른 폼 필드처럼 ISO 문자열로 저장한다.
    event_at: Mapped[str] = mapped_column(String(10), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(20))  # "file" | "form"
    raw_text: Mapped[str] = mapped_column(Text)
    structured: Mapped[dict] = mapped_column(JSON, default=dict)
    extracted_skills: Mapped[list] = mapped_column(JSON, default=list)
    # 경력 축 매칭용. total_years 는 총 경력 연차, target_position 은 POSITION 코드.
    # job_parser/profile_exporter 추측으로 백필되고 이력서 폼에서 수정 가능.
    total_years: Mapped[int] = mapped_column(Integer, default=0)
    target_position: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
