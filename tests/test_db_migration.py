from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as db_module


def _make_isolated_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    assert status == "관심"


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
        row = conn.execute(text("SELECT required_text, source_site FROM job_postings")).one()
    assert row[0] != ""
    filled_required_text = row[0]

    db_module._backfill_job_postings()

    with engine.connect() as conn:
        row_again = conn.execute(text("SELECT required_text FROM job_postings")).one()
    assert row_again[0] == filled_required_text
