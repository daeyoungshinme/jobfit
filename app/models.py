from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


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
    raw_text: Mapped[str] = mapped_column(Text)
    main_tasks: Mapped[str] = mapped_column(Text, default="")
    required_text: Mapped[str] = mapped_column(Text, default="")
    preferred_text: Mapped[str] = mapped_column(Text, default="")
    benefits: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
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
