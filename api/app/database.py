"""SQLAlchemy engine and session setup."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        path = url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args=connect_args)


engine = _make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    # Skeleton convenience: create tables on startup. Swap for Alembic
    # migrations once the schema stabilises (see docs/architecture.md).
    from . import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    add_missing_columns(engine)


def add_missing_columns(bind: Engine) -> None:
    """Add new nullable columns to tables that already exist.

    create_all only creates missing tables, so a column added to an existing
    model (e.g. leagues.owner_id) would otherwise be missing on an existing
    database. Only nullable columns can be added this way, without their
    foreign-key constraint. A stopgap until Alembic.
    """
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue
                if not column.nullable:
                    raise RuntimeError(
                        f"Can't add non-nullable column {table.name}.{column.name} automatically"
                    )
                col_type = column.type.compile(dialect=bind.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'))


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
