"""Import the local prototype database into a Neon/Postgres DATABASE_URL."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from gamepulse.db.importer import SqlAlchemyImportRepository, import_sqlite
from gamepulse.db.session import make_engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import GamePulse SQLite data into Neon/Postgres.")
    parser.add_argument("--sqlite", required=True, type=Path, help="Source SQLite database path")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="Target SQLAlchemy/Postgres URL")
    args = parser.parse_args(argv)

    if not args.database_url:
        print(json.dumps({"error": "DATABASE_URL or --database-url is required"}), file=sys.stderr)
        return 2
    if not args.sqlite.is_file():
        print(json.dumps({"error": "SQLite source does not exist", "sqlite": str(args.sqlite)}), file=sys.stderr)
        return 2

    engine = make_engine(args.database_url)
    try:
        with Session(engine) as session:
            report = import_sqlite(args.sqlite, SqlAlchemyImportRepository(session))
    finally:
        engine.dispose()

    payload = {
        "sqlite": str(args.sqlite),
        "row_counts": report.row_counts,
        "skipped_rows": report.skipped_rows,
        "validation_failures": list(report.validation_failures),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not report.validation_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
