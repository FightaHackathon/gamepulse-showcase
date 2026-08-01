import csv
import tempfile
import unittest
from pathlib import Path

from scripts.build_prototype_database import build_database


class PrototypeDatabaseTests(unittest.TestCase):
    def _write_csv(self, directory: Path, name: str, rows: list[dict[str, object]]) -> None:
        path = directory / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_build_database_loads_normalized_rows_and_enforces_relationships(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            processed = root / "processed"
            processed.mkdir()
            self._write_csv(processed, "games_master.csv", [
                {"steam_app_id": "10", "name": "Alpha", "release_date": "2024-01-01", "price_usd": "10", "owners_low": "100", "owners_high": "200", "peak_ccu": "20", "positive_reviews": "90", "negative_reviews": "10", "total_reviews": "100", "review_score": "0.9", "header_image_url": ""},
                {"steam_app_id": "20", "name": "Beta", "release_date": "2024-02-01", "price_usd": "0", "owners_low": "", "owners_high": "", "peak_ccu": "5", "positive_reviews": "8", "negative_reviews": "2", "total_reviews": "10", "review_score": "0.8", "header_image_url": ""},
            ])
            self._write_csv(processed, "game_tags.csv", [{"steam_app_id": "10", "value": "RPG"}])
            self._write_csv(processed, "game_genres.csv", [{"steam_app_id": "10", "value": "Role-Playing"}])
            self._write_csv(processed, "game_review_summary.csv", [{"steam_app_id": "10", "review_count": "1", "recommended_count": "1", "not_recommended_count": "0", "review_score": "1", "average_playtime_minutes": "60"}, {"steam_app_id": "999", "review_count": "1", "recommended_count": "1", "not_recommended_count": "0", "review_score": "1", "average_playtime_minutes": "60"}])
            self._write_csv(processed, "reviews_clean.csv", [{"review_id": "r1", "steam_app_id": "10", "review_text": "Great", "recommended": "True", "created_at_unix": "1704067200", "author_playtime_minutes": "60"}, {"review_id": "r2", "steam_app_id": "999", "review_text": "Unmatched", "recommended": "False", "created_at_unix": "1704067200", "author_playtime_minutes": "60"}])

            database_path = root / "data" / "prototype.sqlite3"
            report = build_database(processed, database_path)

            self.assertEqual(report.table_counts["games"], 2)
            self.assertEqual(report.table_counts["reviews"], 1)
            self.assertTrue(report.foreign_keys_ok)

            import sqlite3
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM game_tags").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM review_summaries").fetchone()[0], 1)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
