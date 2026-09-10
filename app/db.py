import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.enums import JOB_STATUS_DEFAULT

logger = logging.getLogger("jobfit.db")

DB_PATH = Path(__file__).resolve().parent.parent / "jobfit.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Which one-off data migrations a given jobfit.db still needs is tracked
# entirely by the per-step "done" flags in the schema_meta table (see
# _run_data_migrations). Column additions are idempotent via
# _migrate_table_columns and need no flag at all.

# (column, DDL type, default literal) for JobPosting columns added after the
# table was first created. SQLite has no ALTER-TABLE-based migration tooling
# in this project, so missing columns are detected and added at startup
# instead. The default literal is inserted verbatim into the ALTER TABLE
# statement, so it must match the column's DDL type (e.g. "0" for an
# INTEGER column, "''" for TEXT/VARCHAR).
_JOB_POSTING_NEW_COLUMNS = [
    ("address", "VARCHAR(300)", "''"),
    ("main_tasks", "TEXT", "''"),
    ("required_text", "TEXT", "''"),
    ("preferred_text", "TEXT", "''"),
    ("source_site", "VARCHAR(100)", "''"),
    ("status", "VARCHAR(20)", f"'{JOB_STATUS_DEFAULT}'"),
    ("applied_via", "VARCHAR(30)", "''"),
    ("applied_at", "VARCHAR(10)", "''"),
    ("applied_resume_id", "INTEGER", "0"),
    ("memo", "TEXT", "''"),
    ("is_inbound", "BOOLEAN", "0"),
    ("sections_detected", "BOOLEAN", "0"),
    # SQLite 는 ALTER ADD COLUMN 에 CURRENT_TIMESTAMP 기본값을 못 쓴다 — NULL 로
    # 추가하고 _backfill_updated_at() 이 기존 행을 created_at 으로 채운다.
    ("updated_at", "DATETIME", "NULL"),
    ("employment_type", "VARCHAR(20)", "''"),
    ("remote_policy", "VARCHAR(20)", "''"),
    ("salary_text", "VARCHAR(200)", "''"),
    ("deadline", "VARCHAR(20)", "''"),
    ("benefits_text", "TEXT", "''"),
    ("process_text", "TEXT", "''"),
]

# NOTE: an older jobfit.db may still carry a physical "benefits" column from a
# previous release. SQLite can't drop columns without a table rebuild, so the
# column is left in place and simply ignored — the model no longer maps it.

# Same pattern as _JOB_POSTING_NEW_COLUMNS, for the `resumes` table.
_RESUME_NEW_COLUMNS: list[tuple[str, str, str]] = [
    ("total_years", "INTEGER", "0"),
    ("target_position", "VARCHAR(50)", "''"),
]

class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_table_columns(table_name: str, columns: list[tuple[str, str, str]]) -> None:
    """Add any columns in `columns` missing from `table_name` in an existing jobfit.db.

    `columns` is a list of (column, DDL type, default literal) tuples, e.g.
    _JOB_POSTING_NEW_COLUMNS. The default literal is inserted verbatim into
    the ALTER TABLE statement, so it must match the column's DDL type (e.g.
    "0" for an INTEGER column, "''" for TEXT/VARCHAR).

    Idempotent — only ALTERs columns that are actually missing. Reused for any
    table that grows new columns after its initial release; see
    _JOB_POSTING_NEW_COLUMNS / _RESUME_NEW_COLUMNS for the pattern.
    """
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})"))}
        added = False
        for column, ddl_type, default in columns:
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column} {ddl_type} DEFAULT {default}"))
                added = True
        if added:
            conn.commit()


def _ensure_schema_meta_table() -> None:
    """Create the key/value table that tracks the schema version and which
    one-off data migrations have already run."""
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        )


def _get_meta(key: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT value FROM schema_meta WHERE key = :k"), {"k": key}).first()
    return row[0] if row else None


def _set_meta(key: str, value: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO schema_meta (key, value) VALUES (:k, :v) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            ),
            {"k": key, "v": value},
        )


def _reparse_all_job_postings() -> None:
    """Re-parse every posting's raw_text and (re)fill everything the parser and
    the field guesser derive from it: the section fields + skills, the
    sections_detected flag, and any still-empty best-effort field
    (address / source_site / employment_type / remote_policy / deadline /
    salary_text).

    Consolidates what used to be three separate startup passes
    (_backfill_job_postings, _backfill_sections_detected, _backfill_job_extras),
    each of which re-parsed the same raw_text. Runs once, guarded by a
    schema_meta flag in _run_data_migrations. Parsing is deterministic so a
    re-run is harmless.

    Each row is committed on its own: a single pathological raw_text must not
    abort startup or drag the rows already parsed back down with it, so
    failures are rolled back, logged, and skipped — not raised.
    """
    from sqlalchemy import select

    from app.models import JobPosting
    from app.services.job_parser import (
        apply_parsed_sections,
        guess_posting_fields,
        guess_source_site,
        parse_job_posting,
    )

    db = SessionLocal()
    try:
        ids = list(db.scalars(select(JobPosting.id).where(JobPosting.raw_text != "")))
        for job_id in ids:
            job = db.get(JobPosting, job_id)
            try:
                apply_parsed_sections(job, parse_job_posting(job.raw_text))
                guessed = guess_posting_fields(job.raw_text)
                job.address = job.address or guessed.address
                job.source_site = job.source_site or guess_source_site(job.url)
                job.employment_type = job.employment_type or guessed.employment_type
                job.remote_policy = job.remote_policy or guessed.remote_policy
                job.deadline = job.deadline or guessed.deadline
                job.salary_text = job.salary_text or guessed.salary_text
                db.commit()
            except Exception:
                db.rollback()
                logger.warning("job_posting %s 백필 실패 — 건너뜁니다", job_id, exc_info=True)
    finally:
        db.close()


def _migrate_enum_codes() -> None:
    """Convert Korean-label enum values stored before app/enums.py existed to
    their ascii codes (status/position/experience_level/applied_via). Values
    that don't resolve to a known code or label — free-form experience ranges
    like "2~8년" — are left untouched and logged.
    """
    from sqlalchemy import select, update

    from app.enums import APPLY_CHANNEL, EXPERIENCE_LEVEL, JOB_STATUS, POSITION
    from app.models import JobPosting

    field_enums = {
        "status": JOB_STATUS,
        "position": POSITION,
        "experience_level": EXPERIENCE_LEVEL,
        "applied_via": APPLY_CHANNEL,
    }
    db = SessionLocal()
    try:
        for field, enum_set in field_enums.items():
            col = getattr(JobPosting, field)
            for (value,) in db.execute(select(col).distinct()):
                if not value:
                    continue
                code = enum_set.normalize(value)
                if code is None:
                    # experience_level 은 "3년 이상"·"2~8년" 같은 자유 입력 범위가
                    # 정상이므로 INFO, 나머지 필드의 미상 값은 의심스러우니 WARNING.
                    level = logger.info if field == "experience_level" else logger.warning
                    level("job_postings.%s 값 %r 은 알려진 코드/라벨이 아님 — 그대로 둡니다", field, value)
                elif code != value:
                    db.execute(update(JobPosting).where(col == value).values({field: code}))
        db.commit()
    finally:
        db.close()


def _backfill_updated_at() -> None:
    """New job_postings.updated_at rows land as NULL (SQLite ALTER limitation);
    seed them from created_at so existing postings aren't all "never updated"."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE job_postings SET updated_at = created_at WHERE updated_at IS NULL")
        )


def _backfill_resume_career() -> None:
    """이력서 원문에서 총 경력 연차(total_years)와 목표 직무(target_position)를
    추측해 채운다 — 해당 컬럼 도입 전에 저장된 이력서용. 행 단위로 격리한다."""
    from sqlalchemy import select

    from app.models import Resume
    from app.services.job_parser import guess_position_code
    from app.services.profile_exporter import guess_total_years

    db = SessionLocal()
    try:
        ids = list(db.scalars(select(Resume.id).where(Resume.raw_text != "")))
        for resume_id in ids:
            resume = db.get(Resume, resume_id)
            try:
                if not resume.total_years:
                    resume.total_years = guess_total_years(resume.raw_text) or 0
                if not resume.target_position:
                    resume.target_position = guess_position_code(resume.label, resume.raw_text)
                db.commit()
            except Exception:
                db.rollback()
                logger.warning(
                    "resume %s 경력정보 백필 실패 — 건너뜁니다", resume_id, exc_info=True
                )
    finally:
        db.close()


def _run_data_migrations() -> None:
    """One-off data migrations, each guarded by its own schema_meta flag so it
    runs exactly once per database. Add a new step as another
    `if _get_meta(...) != "done": ...; _set_meta(...)` block."""
    if _get_meta("enum_codes_migrated") != "done":
        _migrate_enum_codes()
        _set_meta("enum_codes_migrated", "done")
    # v2 replaces three older passes (job_postings_backfilled /
    # sections_detected_backfilled / job_extras_backfilled) that each re-parsed
    # raw_text; a DB carrying those old flags simply re-parses once more here.
    if _get_meta("job_postings_reparsed_v2") != "done":
        _reparse_all_job_postings()
        _set_meta("job_postings_reparsed_v2", "done")
    if _get_meta("job_updated_at_backfilled") != "done":
        _backfill_updated_at()
        _set_meta("job_updated_at_backfilled", "done")
    if _get_meta("resume_career_backfilled") != "done":
        _backfill_resume_career()
        _set_meta("resume_career_backfilled", "done")


def init_db():
    from app import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _ensure_schema_meta_table()
    _migrate_table_columns("job_postings", _JOB_POSTING_NEW_COLUMNS)
    _migrate_table_columns("resumes", _RESUME_NEW_COLUMNS)
    _run_data_migrations()
