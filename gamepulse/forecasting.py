"""Leakage-safe baseline forecast used until enough snapshots exist for ML."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class ForecastRange:
    horizon_days: int
    low: int
    expected: int
    high: int
    method: str


@dataclass(frozen=True)
class BacktestReport:
    baseline_mae: float
    candidate_mae: float
    selected_method: str
    folds: int
    train_end_last_fold: int
    test_start_last_fold: int


def _mean(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def backtest_review_forecast(frame: pd.DataFrame, horizon_days: int = 30) -> BacktestReport:
    """Compare two causal baselines using rolling chronological test windows."""
    horizon = max(1, int(horizon_days))
    if not {"date", "count"}.issubset(frame.columns):
        raise ValueError("forecast frame must contain date and count columns")
    ordered = frame.sort_values("date", kind="stable").reset_index(drop=True)
    counts = [max(0, int(value)) for value in ordered["count"].tolist()]
    min_history = max(7, horizon)
    baseline_errors: list[float] = []
    candidate_errors: list[float] = []
    last_train_end = last_test_start = -1
    for cut in range(min_history, len(counts) - horizon + 1, horizon):
        train = counts[:cut]
        test = counts[cut:cut + horizon]
        baseline = _mean(train[-30:])
        candidate = _mean(train[-7:])
        baseline_errors.extend(abs(value - baseline) for value in test)
        candidate_errors.extend(abs(value - candidate) for value in test)
        last_train_end, last_test_start = cut - 1, cut
    if not baseline_errors:
        return BacktestReport(0.0, 0.0, "recent-activity baseline", 0, -1, -1)
    baseline_mae = sum(baseline_errors) / len(baseline_errors)
    candidate_mae = sum(candidate_errors) / len(candidate_errors)
    selected = "trailing-7-day moving average" if candidate_mae < baseline_mae else "recent-activity baseline"
    return BacktestReport(round(baseline_mae, 4), round(candidate_mae, 4), selected, len(baseline_errors) // horizon, last_train_end, last_test_start)


def forecast_review_activity(daily_counts: list[int], horizon_days: int = 30) -> ForecastRange:
    """Select a forecast method only when it beats the recent-activity baseline."""
    horizon = max(1, int(horizon_days))
    counts = [max(0, int(value)) for value in daily_counts]
    frame = pd.DataFrame({"date": range(len(counts)), "count": counts})
    report = backtest_review_forecast(frame, horizon)
    recent = counts[-7:] if report.selected_method == "trailing-7-day moving average" else counts[-30:]
    if not recent:
        return ForecastRange(horizon, 0, 0, 0, report.selected_method)
    expected = round(_mean(recent) * horizon)
    spread = round(max(1.0, (max(recent) - min(recent)) * horizon * 0.25))
    return ForecastRange(horizon, max(0, expected - spread), expected, expected + spread, report.selected_method)


def daily_counts_for_game(database_path: Path, app_id: int) -> list[int]:
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT (created_at_unix / 86400) AS day, COUNT(*) FROM reviews WHERE steam_app_id = ? GROUP BY day ORDER BY day", (app_id,)).fetchall()
    finally:
        connection.close()
    if not rows:
        return []
    counts_by_day = {int(row[0]): int(row[1]) for row in rows}
    first_day, last_day = min(counts_by_day), max(counts_by_day)
    return [counts_by_day.get(day, 0) for day in range(first_day, last_day + 1)]


def forecast_from_daily_counts(daily_counts: list[int], horizon_days: int = 30) -> ForecastRange:
    horizon = max(1, int(horizon_days))
    recent = [max(0, int(value)) for value in daily_counts[-30:]]
    if not recent:
        return ForecastRange(horizon, 0, 0, 0, "recent-activity baseline")
    average = sum(recent) / len(recent)
    expected = round(average * horizon)
    spread = round(max(1.0, (max(recent) - min(recent)) * horizon * 0.25))
    return ForecastRange(horizon, max(0, expected - spread), expected, expected + spread, "recent-activity baseline")
