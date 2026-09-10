"""`init_db()` 오케스트레이션 전체 경로 테스트.

conftest 의 `db_session` 픽스처는 `Base.metadata.create_all` 로 스키마를 바로
만들어 마이그레이션/백필 경로를 타지 않으므로, 여기서는 임시 파일 SQLite 로
실제 `init_db()` 를 구동한다 (실제 `jobfit.db` 는 건드리지 않는다).
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import db as db_module
from app import migrations


def _use_temp_db(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'jobfit_test.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))
    return engine


def test_init_db_creates_schema_and_is_repeatable(monkeypatch, tmp_path):
    engine = _use_temp_db(monkeypatch, tmp_path)

    db_module.init_db()
    db_module.init_db()  # 2회 연속 실행도 예외 없이 끝난다

    with engine.connect() as conn:
        job_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(job_postings)"))}
        backfill_flag = conn.execute(
            text("SELECT value FROM schema_meta WHERE key = 'job_postings_reparsed_v2'")
        ).scalar_one()

    for column, _ddl, _default in migrations._JOB_POSTING_NEW_COLUMNS:
        assert column in job_columns
    assert backfill_flag == "done"

    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
    assert "application_events" in tables  # 신규 테이블도 create_all 로 생성된다


def test_init_db_backfill_runs_once(monkeypatch, tmp_path):
    engine = _use_temp_db(monkeypatch, tmp_path)
    db_module.init_db()

    # 백필 대상(required_text == "") 행을 하나 심는다.
    from app.models import JobPosting

    session = db_module.SessionLocal()
    try:
        session.add(
            JobPosting(
                title="공고", company="회사", position="백엔드",
                raw_text="[자격요건]\nPython", required_text="",
                required_skills=[], preferred_skills=[],
            )
        )
        session.commit()
    finally:
        session.close()

    db_module.init_db()  # 플래그가 이미 있으므로 재파싱이 다시 돌지 않는다

    with engine.connect() as conn:
        required_text = conn.execute(text("SELECT required_text FROM job_postings")).scalar_one()
    assert required_text == ""  # 재파싱이 재실행됐다면 채워졌을 것


def test_init_db_adopts_v2_flag_from_legacy_backfill_flags(monkeypatch, tmp_path):
    """구버전(3개 패스)으로 이미 마이그레이션된 DB: 통합 v2 플래그가 없어도
    구 플래그 3개가 done 이면 재파싱을 다시 돌리지 않고 플래그만 채택한다 —
    onupdate=_now 때문에 updated_at 이 튀는 걸 피한다."""
    engine = _use_temp_db(monkeypatch, tmp_path)
    db_module.init_db()

    from app.models import JobPosting

    session = db_module.SessionLocal()
    try:
        session.add(
            JobPosting(
                title="공고", company="회사", position="백엔드",
                raw_text="[자격요건]\nPython", required_text="",
                required_skills=[], preferred_skills=[],
            )
        )
        session.commit()
    finally:
        session.close()

    # 구버전 상태 재현: v2 플래그 제거, 구 플래그 3개를 done 으로.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM schema_meta WHERE key = 'job_postings_reparsed_v2'"))
    for flag in ("job_postings_backfilled", "sections_detected_backfilled", "job_extras_backfilled"):
        migrations._set_meta(flag, "done")

    db_module.init_db()

    with engine.connect() as conn:
        required_text = conn.execute(text("SELECT required_text FROM job_postings")).scalar_one()
        v2_flag = conn.execute(
            text("SELECT value FROM schema_meta WHERE key = 'job_postings_reparsed_v2'")
        ).scalar_one()
    assert required_text == ""  # 재파싱이 돌지 않았다
    assert v2_flag == "done"    # 플래그만 채택됐다
