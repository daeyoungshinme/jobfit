from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import JOB_STATUS_DEFAULT


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(20))  # "file" | "form"
    raw_text: Mapped[str] = mapped_column(Text)
    structured: Mapped[dict] = mapped_column(JSON, default=dict)
    extracted_skills: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
