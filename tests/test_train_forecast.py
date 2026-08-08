import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.train_forecast import _daily_frame, train_forecast


class TrainForecastTests(unittest.TestCase):
    def test_daily_frame_fills_calendar_days_with_zero_activity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "reviews.sqlite3"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE reviews (steam_app_id INTEGER, created_at_unix INTEGER)")
            connection.executemany("INSERT INTO reviews VALUES (10, ?)", [(86400,), (86400 * 3,)])
            connection.commit()
            connection.close()

            frame = _daily_frame(database, 10)

        self.assertEqual(frame["count"].tolist(), [1, 0, 1])

    def test_training_writes_a_leakage_safe_selection_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "reviews.sqlite3"
            output = Path(temp_dir) / "models"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE reviews (steam_app_id INTEGER, created_at_unix INTEGER)")
            connection.executemany("INSERT INTO reviews VALUES (10, ?)", [(86400 * day,) for day in range(1, 25)])
            connection.commit()
            connection.close()

            artifact_path = train_forecast(database, output, 10, horizon_days=3)
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

        self.assertEqual(artifact["steam_app_id"], 10)
        self.assertEqual(artifact["backtest"]["test_start_last_fold"], artifact["backtest"]["train_end_last_fold"] + 1)
        self.assertIn(artifact["forecast"]["method"], {"recent-activity baseline", "trailing-7-day moving average"})


if __name__ == "__main__":
    unittest.main()
