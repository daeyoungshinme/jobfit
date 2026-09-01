import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import JobPosting, Resume


def make_memory_engine():
    """A throwaway in-memory SQLite engine that survives across connections."""
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def db_session():
    engine = make_memory_engine()
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def make_job():
    """비영속 JobPosting 빌더 — compute_match 등 순수 서비스 함수 테스트용 (DB 불필요)."""
    def _make(id, title, required, preferred, position="백엔드 개발자"):
        job = JobPosting(
            title=title,
            company="테스트",
            position=position,
            raw_text="",
            required_skills=required,
            preferred_skills=preferred,
        )
        job.id = id
        return job

    return _make


@pytest.fixture()
def job_factory(db_session):
    """Persist a JobPosting; keyword args override the defaults."""
    def _make(**overrides):
        fields = {
            "title": "백엔드 개발자 채용",
            "company": "테스트회사",
            "position": "백엔드 개발자",
            "raw_text": "[자격요건]\nPython, Kafka 경험",
            "required_text": "Python, Kafka 경험",
            "required_skills": ["Python", "Kafka"],
            "preferred_skills": [],
        }
        fields.update(overrides)
        job = JobPosting(**fields)
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        return job

    return _make


@pytest.fixture()
def resume_factory(db_session):
    """Persist a Resume (form source by default); keyword args override defaults."""
    def _make(**overrides):
        fields = {
            "label": "테스트 이력서",
            "source_type": "form",
            "raw_text": "[경력]\nPython 백엔드 3년\n\n[프로젝트]\n\n[학력]\n\n[기술 스택]\nPython",
            "structured": {"career": "Python 백엔드 3년", "projects": "", "education": "", "skills_text": "Python"},
            "extracted_skills": ["Python"],
        }
        fields.update(overrides)
        resume = Resume(**fields)
        db_session.add(resume)
        db_session.commit()
        db_session.refresh(resume)
        return resume

    return _make
