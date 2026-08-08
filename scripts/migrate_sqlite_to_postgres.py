from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from gamepulse.db.importer import SqlAlchemyImportRepository, import_sqlite
from gamepulse.db.session import make_engine


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate the GamePulse prototype SQLite data into Postgres.")
    parser.add_argument("sqlite_path", type=Path, help="Path to the source GamePulse SQLite database")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="Target SQLAlchemy/Postgres URL")
    args = parser.parse_args()

    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    engine = make_engine(args.database_url)
    try:
        with Session(engine) as session:
            report = import_sqlite(args.sqlite_path, SqlAlchemyImportRepository(session))
    finally:
        engine.dispose()

    print(
        json.dumps(
            {
                "row_counts": report.row_counts,
                "skipped_rows": report.skipped_rows,
                "validation_failures": list(report.validation_failures),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not report.validation_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
