import logging

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app import db as db_module
from app.services import job_parser

from .conftest import make_memory_engine


def _make_isolated_engine():
    engine = make_memory_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE job_postings (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(200),
                    company VARCHAR(200) DEFAULT '',
                    url VARCHAR(500) DEFAULT '',
                    position VARCHAR(100),
                    experience_level VARCHAR(50) DEFAULT '',
                    raw_text TEXT,
                    required_skills JSON,
                    preferred_skills JSON,
                    created_at DATETIME
                )
                """
            )
        )
    return engine


def test_migrate_table_columns_adds_missing_columns_and_is_idempotent(monkeypatch):
    engine = _make_isolated_engine()
    monkeypatch.setattr(db_module, "engine", engine)

    db_module._migrate_table_columns("job_postings", db_module._JOB_POSTING_NEW_COLUMNS)

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(job_postings)"))}
    for column, _ddl_type, _default in db_module._JOB_POSTING_NEW_COLUMNS:
        assert column in columns

    # Second run is a no-op (does not raise "duplicate column name").
    db_module._migrate_table_columns("job_postings", db_module._JOB_POSTING_NEW_COLUMNS)

    with engine.connect() as conn:
        columns_again = {row[1] for row in conn.execute(text("PRAGMA table_info(job_postings)"))}
    assert columns_again == columns


def test_migrate_resumes_with_empty_column_list_is_noop(monkeypatch):
    engine = _make_isolated_engine()
    monkeypatch.setattr(db_module, "engine", engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE resumes (id INTEGER PRIMARY KEY, label VARCHAR(200))"))

    db_module._migrate_table_columns("resumes", db_module._RESUME_NEW_COLUMNS)

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(resumes)"))}
    assert columns == {"id", "label"}


def test_migrate_backfills_status_default_on_existing_rows(monkeypatch):
    engine = _make_isolated_engine()
    monkeypatch.setattr(db_module, "engine", engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (title, position, raw_text, created_at) "
                "VALUES ('기존 공고', '백엔드', 'x', '2024-01-01')"
            )
        )

    db_module._migrate_table_columns("job_postings", db_module._JOB_POSTING_NEW_COLUMNS)

    with engine.connect() as conn:
        status = conn.execute(text("SELECT status FROM job_postings")).scalar_one()
    assert status == "interest"


def test_migrate_adds_application_columns_with_typed_defaults(monkeypatch):
    engine = _make_isolated_engine()
    monkeypatch.setattr(db_module, "engine", engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (title, position, raw_text, created_at) "
                "VALUES ('기존 공고', '백엔드', 'x', '2024-01-01')"
            )
        )

    db_module._migrate_table_columns("job_postings", db_module._JOB_POSTING_NEW_COLUMNS)

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(job_postings)"))}
        assert {"applied_via", "applied_at", "applied_resume_id", "memo", "is_inbound"} <= columns
        row = conn.execute(
            text(
                "SELECT applied_via, applied_at, applied_resume_id, memo, is_inbound "
                "FROM job_postings"
            )
        ).one()
    assert row[0] == "" and row[1] == "" and row[3] == ""
    assert row[2] == 0  # INTEGER default literal, not the string "0"
    assert not row[4]   # is_inbound defaults falsy


def test_backfill_job_postings_fills_empty_rows_and_is_idempotent(monkeypatch):
    engine = _make_isolated_engine()
    monkeypatch.setattr(db_module, "engine", engine)
    db_module._migrate_table_columns("job_postings", db_module._JOB_POSTING_NEW_COLUMNS)

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(db_module, "SessionLocal", TestingSessionLocal)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO job_postings
                    (title, company, url, position, experience_level, raw_text,
                     required_skills, preferred_skills, address, main_tasks,
                     required_text, preferred_text, source_site, created_at)
                VALUES
                    ('백엔드 개발자', '테스트회사', 'https://example.com/jobs/1', '백엔드', '3년',
                     '[주요업무]\n서비스 개발\n[자격요건]\nPython', '[]', '[]',
                     '', '', '', '', '', '2024-01-01')
                """
            )
        )

    db_module._backfill_job_postings()

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT required_text, source_site, required_skills FROM job_postings")
        ).one()
    assert row[0] != ""
    assert "Python" in row[2]  # skills re-extracted, not left as the stale '[]'
    filled_required_text = row[0]

    db_module._backfill_job_postings()

    with engine.connect() as conn:
        row_again = conn.execute(text("SELECT required_text FROM job_postings")).one()
    assert row_again[0] == filled_required_text


def test_migrate_enum_codes_converts_labels_and_leaves_ranges(monkeypatch, caplog):
    engine = _make_isolated_engine()
    monkeypatch.setattr(db_module, "engine", engine)
    db_module._migrate_table_columns("job_postings", db_module._JOB_POSTING_NEW_COLUMNS)
    monkeypatch.setattr(db_module, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (title, position, experience_level, status, applied_via, "
                "raw_text, required_skills, preferred_skills, address, main_tasks, required_text, "
                "preferred_text, source_site, created_at) VALUES "
                "('a', '백엔드 개발자', '3~5년', '면접', '원티드', 'x', '[]', '[]', '', '', 'x', '', '', '2024-01-01'), "
                "('b', 'backend', '2~8년', '관심', '', 'x', '[]', '[]', '', '', 'x', '', '', '2024-01-01')"
            )
        )

    import logging

    with caplog.at_level(logging.INFO, logger="jobfit.db"):
        db_module._migrate_enum_codes()

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT title, position, experience_level, status FROM job_postings ORDER BY title")
        ).all()
    assert rows[0] == ("a", "backend", "y3_5", "interview")   # 라벨 → 코드
    assert rows[1] == ("b", "backend", "2~8년", "interest")   # 이미 코드 / 범위는 보존
    assert any("2~8년" in r.message for r in caplog.records)  # 미상 값 로깅


def test_backfill_sections_detected(monkeypatch):
    engine = _make_isolated_engine()
    monkeypatch.setattr(db_module, "engine", engine)
    db_module._migrate_table_columns("job_postings", db_module._JOB_POSTING_NEW_COLUMNS)
    monkeypatch.setattr(db_module, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))

    from app.models import JobPosting

    s = db_module.SessionLocal()
    try:
        s.add_all([
            JobPosting(title="헤더 있음", position="backend",
                       raw_text="[자격요건]\nPython\n[우대사항]\nAWS", required_skills=[], preferred_skills=[]),
            JobPosting(title="헤더 없음", position="backend",
                       raw_text="그냥 줄글로만 된 공고입니다", required_skills=[], preferred_skills=[]),
        ])
        s.commit()
    finally:
        s.close()

    db_module._backfill_sections_detected()

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT title, sections_detected FROM job_postings")).all())
    assert rows["헤더 있음"]
    assert not rows["헤더 없음"]


def test_backfill_isolates_a_failing_row_and_logs_it(monkeypatch, caplog):
    engine = _make_isolated_engine()
    monkeypatch.setattr(db_module, "engine", engine)
    db_module._migrate_table_columns("job_postings", db_module._JOB_POSTING_NEW_COLUMNS)
    monkeypatch.setattr(db_module, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (title, position, raw_text, required_skills, preferred_skills, "
                "address, main_tasks, required_text, preferred_text, source_site, created_at) VALUES "
                "('정상', '백엔드', '[자격요건]\nPython', '[]', '[]', '', '', '', '', '', '2024-01-01'), "
                "('폭탄', '백엔드', 'BOOM', '[]', '[]', '', '', '', '', '', '2024-01-01')"
            )
        )

    real_parse = job_parser.parse_job_posting

    def flaky_parse(raw_text):
        if "BOOM" in raw_text:
            raise ValueError("pathological posting")
        return real_parse(raw_text)

    monkeypatch.setattr(job_parser, "parse_job_posting", flaky_parse)

    with caplog.at_level(logging.WARNING, logger="jobfit.db"):
        db_module._backfill_job_postings()  # 예외를 밖으로 던지지 않는다

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT title, required_text FROM job_postings")).all())
    assert rows["정상"] != ""       # 정상 행은 채워짐
    assert rows["폭탄"] == ""       # 실패 행은 건너뜀
    assert any("백필 실패" in r.message for r in caplog.records)
