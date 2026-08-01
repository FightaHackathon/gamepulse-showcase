import unittest
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd

from gamepulse.forecasting import backtest_review_forecast, daily_counts_for_game, forecast_from_daily_counts


class ForecastingTests(unittest.TestCase):
    def test_forecast_is_nonnegative_and_returns_ordered_range(self):
        result = forecast_from_daily_counts([0, 2, 1, 3, 2], horizon_days=30)

        self.assertGreaterEqual(result.low, 0)
        self.assertLessEqual(result.low, result.expected)
        self.assertLessEqual(result.expected, result.high)
        self.assertEqual(result.method, "recent-activity baseline")

    def test_daily_counts_are_grouped_for_one_game(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE reviews (steam_app_id INTEGER, created_at_unix INTEGER)")
            connection.executemany("INSERT INTO reviews VALUES (10, ?)", [(86400,), (86400,), (172800,)])
            connection.commit()
            connection.close()

            counts = daily_counts_for_game(path, 10)

        self.assertEqual(counts, [2, 1])

    def test_daily_counts_fill_calendar_days_with_zero_activity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE reviews (steam_app_id INTEGER, created_at_unix INTEGER)")
            connection.executemany("INSERT INTO reviews VALUES (10, ?)", [(86400,), (259200,)])
            connection.commit()
            connection.close()

            counts = daily_counts_for_game(path, 10)

        self.assertEqual(counts, [1, 0, 1])

    def test_backtest_uses_chronological_folds_and_selects_only_a_winning_candidate(self):
        frame = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=12, freq="D"),
            "count": [1, 1, 1, 1, 1, 1, 1, 5, 5, 5, 5, 5],
        })

        report = backtest_review_forecast(frame, horizon_days=2)

        self.assertGreaterEqual(report.folds, 1)
        self.assertIn(report.selected_method, {"recent-activity baseline", "trailing-7-day moving average"})
        self.assertLessEqual(report.train_end_last_fold, report.test_start_last_fold)
        self.assertGreaterEqual(report.baseline_mae, 0)
        self.assertGreaterEqual(report.candidate_mae, 0)


if __name__ == "__main__":
    unittest.main()
