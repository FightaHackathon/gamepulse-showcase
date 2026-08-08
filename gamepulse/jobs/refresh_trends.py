"""Refresh persisted trend scores without rewriting the full catalog."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import time

from sqlalchemy.orm import Session

from gamepulse.db.models import Base
from gamepulse.db.session import make_engine
from gamepulse.jobs.import_full_database import _import_trends, _parse_timestamp, _record_provider_run


def run_trend_refresh(database_url: str, *, batch_size: int = 2000, observed_at: datetime | str | None = None) -> dict[str, object]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    started_clock = time.monotonic()
    started_at = datetime.now(timezone.utc)
    trend_time = _parse_timestamp(observed_at) or started_at
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            count = _import_trends(session, trend_time, batch_size, compact_components=True)
            _record_provider_run(
                session,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                status="success",
                metrics_written=count,
            )
            session.commit()
    finally:
        engine.dispose()
    return {
        "status": "success",
        "trend_scores": count,
        "compact_components": True,
        "observed_at": trend_time.isoformat(),
        "import_seconds": round(time.monotonic() - started_clock, 3),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh compact trend scores from the existing Fusion catalog.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="Target SQLAlchemy DATABASE_URL (or DATABASE_URL environment variable).")
    parser.add_argument("--batch-size", type=int, default=2000, help="Rows per database upsert batch.")
    parser.add_argument("--observed-at", help="Stable ISO-8601 timestamp for derived trend scores.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.database_url:
            raise ValueError("DATABASE_URL is required")
        print(json.dumps(run_trend_refresh(args.database_url, batch_size=args.batch_size, observed_at=args.observed_at), sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failure", "error": str(exc)[:500]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
