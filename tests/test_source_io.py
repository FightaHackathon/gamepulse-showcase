import csv
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from gamepulse_data.source_io import open_zip_csv, parse_delimited_values


class SourceIoTests(unittest.TestCase):
    def test_parse_delimited_values_removes_empty_duplicate_values(self):
        self.assertEqual(parse_delimited_values("Action, RPG,Action, "), ["Action", "RPG"])

    def test_open_zip_csv_reads_named_member(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "games.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("games.csv", "AppID,Name\n10,Example\n")
            with open_zip_csv(archive_path, "games.csv") as rows:
                self.assertEqual(list(rows), [{"AppID": "10", "Name": "Example"}])

    def test_catalogue_header_repair_keeps_genres_and_tags_aligned(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "dataset.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("games.csv", "AppID,DiscountDLC count,Genres,Tags,Screenshots\n10,0,1,Action,RPG,shot.jpg\n")
            with open_zip_csv(archive_path, "games.csv") as rows:
                row = next(rows)

        self.assertEqual(row["Discount"], "0")
        self.assertEqual(row["DLC count"], "1")
        self.assertEqual(row["Genres"], "Action")
        self.assertEqual(row["Tags"], "RPG")
