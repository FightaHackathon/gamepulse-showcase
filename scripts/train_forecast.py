"""Create a small, reproducible forecast-selection artifact for one game."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from gamepulse.forecasting import backtest_review_forecast, forecast_review_activity


def _daily_frame(database_path: Path, app_id: int) -> pd.DataFrame:
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute(
            "SELECT date(created_at_unix, 'unixepoch') AS date, COUNT(*) AS count "
            "FROM reviews WHERE steam_app_id = ? GROUP BY date ORDER BY date",
            (app_id,),
        ).fetchall()
    finally:
        connection.close()
    frame = pd.DataFrame(rows, columns=["date", "count"])
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.set_index("date").asfreq("D", fill_value=0).rename_axis("date").reset_index()
    frame["count"] = frame["count"].astype(int)
    return frame


def train_forecast(database_path: Path, output_dir: Path, app_id: int, horizon_days: int = 30) -> Path:
    frame = _daily_frame(database_path, app_id)
    report = backtest_review_forecast(frame, horizon_days)
    forecast = forecast_review_activity(frame["count"].tolist(), horizon_days)
    artifact = {
        "steam_app_id": int(app_id),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "horizon_days": horizon_days,
        "observations": int(len(frame)),
        "backtest": {
            "baseline_mae": report.baseline_mae,
            "candidate_mae": report.candidate_mae,
            "selected_method": report.selected_method,
            "folds": report.folds,
            "train_end_last_fold": report.train_end_last_fold,
            "test_start_last_fold": report.test_start_last_fold,
        },
        "forecast": {
            "low": forecast.low,
            "expected": forecast.expected,
            "high": forecast.high,
            "method": forecast.method,
        },
        "limitations": "Forecasts dated review activity, not verified sales or downloads.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"review_forecast_{app_id}.json"
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--app-id", type=int, required=True)
    args = parser.parse_args()
    print(train_forecast(args.database, args.output, args.app_id))


if __name__ == "__main__":
    main()
