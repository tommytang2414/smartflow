"""Explicit, repeatable v2 schema creation entry point."""

import argparse
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from smartflow.db.models_v2 import V2Base


V2_TABLES = frozenset(V2Base.metadata.tables)


def create_v2_schema(bind: Engine) -> None:
    """Create only v2 tables and indices; never mutate legacy table definitions."""
    V2Base.metadata.create_all(bind=bind)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the isolated SmartFlow v2 schema")
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Explicit SQLite database path; use a verified copy before production",
    )
    args = parser.parse_args()
    database_path = args.database.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path}")
    try:
        create_v2_schema(engine)
    finally:
        engine.dispose()
    print(f"Created/verified v2 schema in {database_path}")


if __name__ == "__main__":
    main()
