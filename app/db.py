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


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_table_columns(table_name: str, columns: list[tuple[str, str, str]]) -> bool:
    """Add any columns in `columns` missing from `table_name` in an existing jobfit.db.

    `columns` is a list of (column, DDL type, default literal) tuples, e.g.
    _JOB_POSTING_NEW_COLUMNS. The default literal is inserted verbatim into
    the ALTER TABLE statement, so it must match the column's DDL type (e.g.
    "0" for an INTEGER column, "''" for TEXT/VARCHAR).

    Returns True if at least one column was added (i.e. this is an upgrade
    from an older schema, not a fresh database), so the caller knows whether
    a backfill pass over existing rows is needed. Reused for any table that
    grows new columns after its initial release — see _JOB_POSTING_NEW_COLUMNS
    for the pattern to follow when Resume needs the same treatment.
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
        return added


def _backfill_job_postings() -> None:
    """Re-derive the new section/address fields for postings saved before this migration."""
    from sqlalchemy import select

    from app.models import JobPosting
    from app.services.job_parser import guess_posting_fields, guess_source_site, parse_job_posting

    db = SessionLocal()
    try:
        jobs = db.scalars(
            select(JobPosting).where(JobPosting.required_text == "", JobPosting.raw_text != "")
        )
        for job in jobs:
            parsed = parse_job_posting(job.raw_text)
            job.main_tasks = parsed.main_tasks_text
            job.required_text = parsed.required_text
            job.preferred_text = parsed.preferred_text
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
    # Always re-run: the backfill query itself is idempotent (only touches rows
    # with required_text == ""), so this also self-heals rows left over from a
    # prior run that added the columns but failed partway through backfilling.
    _backfill_job_postings()
