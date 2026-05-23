from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()


def ensure_schema_compatibility() -> None:
    """Apply small additive schema updates for MVP installs without Alembic."""
    inspector = inspect(engine)
    if "detected_technologies" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("detected_technologies")}
    additions = {
        "evidence_file": "VARCHAR(500)",
        "reason": "TEXT",
        "confidence": "VARCHAR(40)",
    }
    with engine.begin() as connection:
        for column_name, column_type in additions.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE detected_technologies ADD COLUMN {column_name} {column_type}"))

    if "findings" in inspector.get_table_names():
        finding_columns = {column["name"] for column in inspector.get_columns("findings")}
        finding_additions = {
            "priority": "VARCHAR(20)",
            "why_it_matters": "TEXT",
        }
        with engine.begin() as connection:
            for column_name, column_type in finding_additions.items():
                if column_name not in finding_columns:
                    connection.execute(text(f"ALTER TABLE findings ADD COLUMN {column_name} {column_type}"))
