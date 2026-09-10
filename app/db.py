import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger("jobfit.db")

DB_PATH = Path(__file__).resolve().parent.parent / "jobfit.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Import here (not at module level) so `app.db` stays importable before
    # `app.models` / `app.migrations` exist — `app.models` imports `Base` from
    # this module, and `app.migrations` imports this module.
    from app import migrations, models  # noqa: F401  (models: register on Base.metadata)

    Base.metadata.create_all(bind=engine)
    migrations.run_migrations()
