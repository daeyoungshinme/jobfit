import logging

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app import db as db_module
from app import migrations
from app.services import job_parser

from .conftest import make_memory_engine

# Pre-migration ("v1") DDL for the tables these tests exercise, kept in ONE
# place. The migration tests must start from a schema that predates the columns
# _migrate_table_columns adds, so they can't use Base.metadata.create_all
# (which builds today's schema). Copy-pasting CREATE TABLE per test lets a
# column added to models.py without a matching _JOB_POSTING_NEW_COLUMNS /
# _RESUME_NEW_COLUMNS entry drift by silently; defining it once surfaces it.
_LEGACY_DDL = {
    "job_postings": """
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
    """,
    "resumes": """
        CREATE TABLE resumes (
            id INTEGER PRIMARY KEY,
            label VARCHAR(200),
            source_type VARCHAR(20),
            raw_text TEXT,
            structured JSON,
            extracted_skills JSON,
            created_at DATETIME,
            updated_at DATETIME
        )
    """,
}


def _legacy_engine(*tables):
    """In-memory engine with the named tables at their pre-migration schema.
    Defaults to ('job_postings',)."""
    engine = make_memory_engine()
    with engine.begin() as conn:
        for table in tables or ("job_postings",):
            conn.execute(text(_LEGACY_DDL[table]))
    return engine


def _use_legacy_db(monkeypatch, *tables):
    """_legacy_engine + repoint app.db.engine / SessionLocal at it — the
    monkeypatch dance every migration test otherwise repeats."""
    engine = _legacy_engine(*tables)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(
        db_module, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False)
    )
    return engine


def test_legacy_ddl_plus_migrations_reconstructs_todays_schema():
    """The v1 DDL above + the columns _migrate_table_columns adds must equal
    today's model schema. A column added to models.py without a matching
    _JOB_POSTING_NEW_COLUMNS / _RESUME_NEW_COLUMNS entry fails here instead of
    leaving already-migrated databases missing the column."""
    from sqlalchemy import create_engine

    from app.models import JobPosting, Resume

    for model, new_columns, ddl in (
        (JobPosting, migrations._JOB_POSTING_NEW_COLUMNS, _LEGACY_DDL["job_postings"]),
        (Resume, migrations._RESUME_NEW_COLUMNS, _LEGACY_DDL["resumes"]),
    ):
        legacy = create_engine("sqlite://")
        with legacy.begin() as conn:
            conn.execute(text(ddl))
            legacy_cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({model.__tablename__})"))}
        migrated = legacy_cols | {name for name, _ddl, _default in new_columns}
        model_cols = set(model.__table__.columns.keys())
        assert model_cols <= migrated, f"{model.__tablename__}: {model_cols - migrated} not covered by migrations"


def test_migrate_table_columns_adds_missing_columns_and_is_idempotent(monkeypatch):
    engine = _use_legacy_db(monkeypatch)

    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(job_postings)"))}
    for column, _ddl_type, _default in migrations._JOB_POSTING_NEW_COLUMNS:
        assert column in columns

    # Second run is a no-op (does not raise "duplicate column name").
    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

    with engine.connect() as conn:
        columns_again = {row[1] for row in conn.execute(text("PRAGMA table_info(job_postings)"))}
    assert columns_again == columns


def test_migrate_resumes_adds_career_columns_with_typed_defaults(monkeypatch):
    engine = _use_legacy_db(monkeypatch, "resumes")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO resumes (label) VALUES ('기존 이력서')"))

    migrations._migrate_table_columns("resumes", migrations._RESUME_NEW_COLUMNS)

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(resumes)"))}
        assert {"total_years", "target_position"} <= columns
        row = conn.execute(text("SELECT total_years, target_position FROM resumes")).one()
    assert row[0] == 0  # INTEGER default literal, not the string "0"
    assert row[1] == ""

    # Second run is a no-op.
    migrations._migrate_table_columns("resumes", migrations._RESUME_NEW_COLUMNS)
    with engine.connect() as conn:
        columns_again = {row[1] for row in conn.execute(text("PRAGMA table_info(resumes)"))}
    assert columns_again == columns


def test_migrate_backfills_status_default_on_existing_rows(monkeypatch):
    engine = _use_legacy_db(monkeypatch)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (title, position, raw_text, created_at) "
                "VALUES ('기존 공고', '백엔드', 'x', '2024-01-01')"
            )
        )

    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

    with engine.connect() as conn:
        status = conn.execute(text("SELECT status FROM job_postings")).scalar_one()
    assert status == "interest"


def test_migrate_adds_application_columns_with_typed_defaults(monkeypatch):
    engine = _use_legacy_db(monkeypatch)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (title, position, raw_text, created_at) "
                "VALUES ('기존 공고', '백엔드', 'x', '2024-01-01')"
            )
        )

    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

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


def test_reparse_fills_empty_rows_and_is_idempotent(monkeypatch):
    engine = _use_legacy_db(monkeypatch)
    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

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

    migrations._reparse_all_job_postings()

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT required_text, source_site, required_skills FROM job_postings")
        ).one()
    assert row[0] != ""
    assert "Python" in row[2]  # skills re-extracted, not left as the stale '[]'
    filled_required_text = row[0]

    migrations._reparse_all_job_postings()

    with engine.connect() as conn:
        row_again = conn.execute(text("SELECT required_text FROM job_postings")).one()
    assert row_again[0] == filled_required_text


def test_migrate_enum_codes_converts_labels_and_leaves_ranges(monkeypatch, caplog):
    engine = _use_legacy_db(monkeypatch)
    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

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
        migrations._migrate_enum_codes()

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT title, position, experience_level, status FROM job_postings ORDER BY title")
        ).all()
    assert rows[0] == ("a", "backend", "y3_5", "interview")   # 라벨 → 코드
    assert rows[1] == ("b", "backend", "2~8년", "interest")   # 이미 코드 / 범위는 보존
    assert any("2~8년" in r.message for r in caplog.records)  # 미상 값 로깅


def test_reparse_reparses_sections_and_guesses_extras(monkeypatch):
    engine = _use_legacy_db(monkeypatch)
    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

    from app.models import JobPosting

    s = db_module.SessionLocal()
    try:
        s.add(JobPosting(
            title="공고", position="backend",
            raw_text="계약직 채용, 완전 재택.\n[자격요건]\nPython\n[복지 및 혜택]\n- 맥북",
            required_skills=[], preferred_skills=[],
        ))
        s.commit()
    finally:
        s.close()

    migrations._reparse_all_job_postings()

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT employment_type, remote_policy, benefits_text FROM job_postings")
        ).one()
    assert row[0] == "contract"
    assert row[1] == "remote"
    assert "맥북" in row[2]


def test_backfill_resume_career_guesses_years_and_position(monkeypatch):
    engine = _use_legacy_db(monkeypatch, "resumes")
    migrations._migrate_table_columns("resumes", migrations._RESUME_NEW_COLUMNS)

    from app.models import Resume

    s = db_module.SessionLocal()
    try:
        s.add(Resume(
            label="백엔드 이력서", source_type="form",
            raw_text="[경력]\n7년차 백엔드 개발자, Python/FastAPI\n[기술 스택]\nPython",
            structured={}, extracted_skills=["Python"],
        ))
        s.commit()
    finally:
        s.close()

    migrations._backfill_resume_career()

    with engine.connect() as conn:
        row = conn.execute(text("SELECT total_years, target_position FROM resumes")).one()
    assert row[0] == 7
    assert row[1] == "backend"

    # 멱등: 이미 채워진 행은 그대로.
    migrations._backfill_resume_career()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT total_years FROM resumes")).scalar_one() == 7


def test_backfill_updated_at_seeds_from_created_at(monkeypatch):
    engine = _use_legacy_db(monkeypatch)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (title, position, raw_text, created_at) "
                "VALUES ('오래된 공고', 'backend', 'x', '2024-01-01 09:00:00')"
            )
        )

    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)
    migrations._backfill_updated_at()

    with engine.connect() as conn:
        created, updated = conn.execute(
            text("SELECT created_at, updated_at FROM job_postings")
        ).one()
    assert updated == created

    # 멱등: 두 번째 실행은 이미 채워진 행을 건드리지 않는다.
    migrations._backfill_updated_at()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT updated_at FROM job_postings")).scalar_one() == created


def test_reparse_sets_sections_detected(monkeypatch):
    engine = _use_legacy_db(monkeypatch)
    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

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

    migrations._reparse_all_job_postings()

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT title, sections_detected FROM job_postings")).all())
    assert rows["헤더 있음"]
    assert not rows["헤더 없음"]


def test_backfill_isolates_a_failing_row_and_logs_it(monkeypatch, caplog):
    engine = _use_legacy_db(monkeypatch)
    migrations._migrate_table_columns("job_postings", migrations._JOB_POSTING_NEW_COLUMNS)

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
        migrations._reparse_all_job_postings()  # 예외를 밖으로 던지지 않는다

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT title, required_text FROM job_postings")).all())
    assert rows["정상"] != ""       # 정상 행은 채워짐
    assert rows["폭탄"] == ""       # 실패 행은 건너뜀
    assert any("백필 실패" in r.message for r in caplog.records)
