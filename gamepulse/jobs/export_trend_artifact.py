"""Build a compact gzipped trend dataset for web deployment."""

from __future__ import annotations

import argparse
from datetime import datetime
import gzip
import json
from pathlib import Path
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from gamepulse.db.models import TrendScoreModel
from gamepulse.db.session import make_engine
from gamepulse.jobs.import_full_database import _compact_trend_components, run_full_import


DEFAULT_OUTPUT = Path("gamepulse/assets/trend_scores.json.gz")


def export_trend_artifact(
    sqlite_path: Path | str,
    output_path: Path | str = DEFAULT_OUTPUT,
    *,
    batch_size: int = 2000,
    observed_at: datetime | str | None = None,
) -> dict[str, object]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gamepulse-trend-staging-") as temporary:
        staging = Path(temporary) / "catalog.sqlite3"
        run_full_import(sqlite_path, f"sqlite+pysqlite:///{staging}", batch_size=batch_size, observed_at=observed_at, skip_raw_reviews=True)
        engine = make_engine(f"sqlite+pysqlite:///{staging}")
        try:
            with Session(engine) as session, gzip.open(output, "wt", encoding="utf-8") as handle:
                rows = []
                for row in session.scalars(select(TrendScoreModel).order_by(TrendScoreModel.steam_app_id, TrendScoreModel.audience)):
                    rows.append(
                        {
                            "steam_app_id": row.steam_app_id,
                            "audience": row.audience,
                            "score": row.score,
                            "components": _compact_trend_components(row.audience, row.components),
                            "observed_at": row.observed_at.isoformat(),
                            "source_name": row.source_name,
                            "source_mode": row.source_mode,
                            "confidence": row.confidence,
                        }
                    )
                json.dump(rows, handle, separators=(",", ":"))
        finally:
            engine.dispose()
    return {"status": "success", "output": str(output), "rows": len(rows), "bytes": output.stat().st_size}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export compact trend scores as a gzipped web artifact.")
    parser.add_argument("--sqlite", default="data/prototype/gamepulse_prototype.sqlite3", help="Recovered SQLite source path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output .json.gz path bundled with the web/API deployment.")
    parser.add_argument("--batch-size", type=int, default=2000, help="Rows per local staging upsert batch.")
    parser.add_argument("--observed-at", help="Stable ISO-8601 timestamp for derived trend scores.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        print(json.dumps(export_trend_artifact(args.sqlite, args.output, batch_size=args.batch_size, observed_at=args.observed_at), sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failure", "error": str(exc)[:500]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
