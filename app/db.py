from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "jobfit.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

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
    ("status", "VARCHAR(20)", "'관심'"),
]

# NOTE: an older jobfit.db may still carry a physical "benefits" column from a
# previous release. SQLite can't drop columns without a table rebuild, so the
# column is left in place and simply ignored — the model no longer maps it.

# Same pattern as _JOB_POSTING_NEW_COLUMNS, for the `resumes` table. Empty for
# now — the wiring exists so a future Resume column just needs an entry here
# (plus a dedicated backfill call in init_db() if existing rows must be filled).
_RESUME_NEW_COLUMNS: list[tuple[str, str, str]] = []


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


def _backfill_job_postings() -> None:
    """Re-derive the section fields, address, and source_site for postings saved
    before those columns existed (or left half-filled by an interrupted run)."""
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
        jobs = db.scalars(
            select(JobPosting).where(JobPosting.required_text == "", JobPosting.raw_text != "")
        )
        for job in jobs:
            apply_parsed_sections(job, parse_job_posting(job.raw_text))
            if not job.address:
                job.address = guess_posting_fields(job.raw_text).address

        for job in db.scalars(select(JobPosting).where(JobPosting.source_site == "", JobPosting.url != "")):
            job.source_site = guess_source_site(job.url)

        db.commit()
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _migrate_table_columns("job_postings", _JOB_POSTING_NEW_COLUMNS)
    _migrate_table_columns("resumes", _RESUME_NEW_COLUMNS)
    # Always re-run: the backfill query itself is idempotent (only touches rows
    # with required_text == ""), so this also self-heals rows left over from a
    # prior run that added the columns but failed partway through backfilling.
    _backfill_job_postings()
