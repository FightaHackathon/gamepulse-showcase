import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.prepare_datasets import prepare_datasets, verify_outputs


class PrepareDatasetTests(unittest.TestCase):
    def _write_archive(self, path: Path, member: str, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(path, "w") as archive:
            archive.writestr(member, contents)

    def test_prepare_datasets_writes_all_required_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            self._write_archive(
                raw_root / "steam-games-dataset" / "dataset.zip",
                "games.csv",
                "AppID,Name,Release date,Estimated owners,Peak CCU,Price,Positive,Negative,Windows,Mac,Linux,Genres,Tags,Developers,Publishers,Categories\n"
                "10,Example,\"Jan 1, 2024\",\"20,000 - 50,000\",5,12.5,90,10,True,False,False,\"Action,RPG\",Action,Studio,Publisher,Single-player\n",
            )
            self._write_archive(
                raw_root / "steam-game-reviews-of-743-games" / "dataset.zip",
                "steam_game_reviews_730945.csv",
                "appid,review,word_count,voted_up,votes_up,votes_funny,timestamp_created,author_playtime_forever,name,price,release_date\n"
                "10,Great game,2,True,1,0,1,10,Example,1250,2024-01-01\n",
            )
            self._write_archive(
                raw_root / "steam-games-dataset-steamspy-api" / "dataset.zip",
                "steam_games_dataset.csv",
                "appid,name,developer,publisher,score_rank,positive,negative,userscore,owners,average_forever,average_2weeks,median_forever,median_2weeks,price,initialprice,discount,ccu\n"
                "10,Example,Studio,Publisher,,90,10,0,\"20,000 .. 50,000\",10,0,10,0,1250,1250,0,5\n",
            )
            (raw_root / "manifest.json").write_text(json.dumps([]), encoding="utf-8")
            report = prepare_datasets(raw_root, root / "processed")
            self.assertTrue((root / "processed" / "games_master.csv").exists())
            self.assertTrue((root / "processed" / "reviews_clean.csv").exists())
            self.assertTrue(report["validations"]["game_ids_unique"])
            verified = verify_outputs(root / "processed")
            self.assertTrue(verified["validations"]["review_summary_reconciles"])
