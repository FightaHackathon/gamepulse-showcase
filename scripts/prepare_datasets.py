from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gamepulse_data.games import GAME_BRIDGE_FIELDS, build_game_bridges, game_master_row, normalise_game_row
from gamepulse_data.reviews import ReviewSummaryAccumulator, normalise_review_row
from gamepulse_data.source_io import open_zip_csv


CATALOGUE_ARCHIVE = "steam-games-dataset/dataset.zip"
CATALOGUE_MEMBER = "games.csv"
REVIEWS_ARCHIVE = "steam-game-reviews-of-743-games/dataset.zip"
REVIEWS_MEMBER = "steam_game_reviews_730945.csv"
STEAMSPY_ARCHIVE = "steam-games-dataset-steamspy-api/dataset.zip"
STEAMSPY_MEMBER = "steam_games_dataset.csv"

GAME_FIELDS = [
    "steam_app_id", "name", "release_date", "price_usd", "discount_pct",
    "required_age", "owners_low", "owners_high", "peak_ccu", "positive_reviews",
    "negative_reviews", "total_reviews", "review_score", "recommendations",
    "average_playtime_minutes", "median_playtime_minutes", "windows", "mac",
    "linux", "metacritic_score", "header_image_url", "website_url", "short_description",
]
REVIEW_FIELDS = [
    "review_id", "steam_app_id", "review_text", "word_count", "recommended",
    "helpful_votes", "funny_votes", "created_at_unix", "author_playtime_minutes",
    "source_game_name", "source_price", "source_release_date",
]
REVIEW_SUMMARY_FIELDS = [
    "steam_app_id", "review_count", "recommended_count", "not_recommended_count",
    "review_score", "helpful_votes_total", "funny_votes_total", "average_word_count",
    "average_playtime_minutes", "latest_review_created_at_unix",
]
FEATURE_FIELDS = [
    "steam_app_id", "name", "release_date", "price_usd", "owners_low", "owners_high",
    "peak_ccu", "catalogue_review_count", "catalogue_review_score", "processed_review_count",
    "processed_review_score", "genre_count", "tag_count", "developer_count", "publisher_count",
    "category_count", "windows", "mac", "linux",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_writer(stack: ExitStack, path: Path, fieldnames: list[str]) -> csv.DictWriter:
    handle = stack.enter_context(path.open("w", encoding="utf-8", newline=""))
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    return writer


def _load_steamspy(archive_path: Path) -> dict[int, dict[str, str]]:
    steamspy: dict[int, dict[str, str]] = {}
    with open_zip_csv(archive_path, STEAMSPY_MEMBER) as rows:
        for row in rows:
            try:
                steamspy[int(row["appid"])] = row
            except (KeyError, TypeError, ValueError):
                continue
    return steamspy


def _write_readme(output_root: Path, report: dict[str, Any]) -> None:
    rows = report["output_rows"]
    text = f"""# GamePulse prepared datasets

Generated: {report["generated_at"]}

These files are analysis-ready outputs for the local GamePulse prototype. The raw source archives remain unchanged in `{report["raw_root"]}`.

| File | Rows | Purpose | Primary key |
|---|---:|---|---|
| `games_master.csv` | {rows["games_master"]:,} | One normalized Steam game per row. | `steam_app_id` |
| `game_genres.csv` | {rows["game_genres"]:,} | Game-to-genre bridge. | `steam_app_id`, `value` |
| `game_tags.csv` | {rows["game_tags"]:,} | Game-to-tag bridge. | `steam_app_id`, `value` |
| `game_developers.csv` | {rows["game_developers"]:,} | Game-to-developer bridge. | `steam_app_id`, `value` |
| `game_publishers.csv` | {rows["game_publishers"]:,} | Game-to-publisher bridge. | `steam_app_id`, `value` |
| `game_categories.csv` | {rows["game_categories"]:,} | Game-to-category bridge. | `steam_app_id`, `value` |
| `reviews_clean.csv` | {rows["reviews_clean"]:,} | Non-empty, deduplicated Steam reviews; language is not yet classified. | `review_id` |
| `game_review_summary.csv` | {rows["game_review_summary"]:,} | Review metrics aggregated per game. | `steam_app_id` |
| `game_features.csv` | {rows["game_features"]:,} | Compact dashboard/recommendation features. | `steam_app_id` |

## Refresh rules

- Re-run `python scripts/prepare_datasets.py --raw-root data/raw/2026-07-30 --output-root data/processed/2026-08-01` after replacing the raw snapshots.
- Keep the raw source folders immutable; select a new processed date for a new transformation run.
- Twitch and IGDB observations are not part of this static preparation. They will be collected separately while the prototype computer is running.

## Limitations

- Steam owner counts are estimates.
- `review_score` is a ratio of positive/recommended reviews to all reviews, not a revenue or sales measure.
- Review language has not been verified in this pass; English-only NLP filtering belongs in the review-analysis stage.
- Streamer, Twitch trend, and IGDB enrichment data are intentionally absent from these static files.
"""
    (output_root / "README.md").write_text(text, encoding="utf-8")


def prepare_datasets(raw_root: Path, output_root: Path) -> dict[str, Any]:
    """Create validated GamePulse CSV datasets without mutating raw archives."""
    raw_root = raw_root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    catalogue_path = raw_root / CATALOGUE_ARCHIVE
    reviews_path = raw_root / REVIEWS_ARCHIVE
    steamspy_path = raw_root / STEAMSPY_ARCHIVE
    for source in (catalogue_path, reviews_path, steamspy_path):
        if not source.exists():
            raise FileNotFoundError(f"Required source archive is missing: {source}")

    steamspy = _load_steamspy(steamspy_path)
    output_rows = {
        "games_master": 0, "game_genres": 0, "game_tags": 0,
        "game_developers": 0, "game_publishers": 0, "game_categories": 0,
        "reviews_clean": 0, "game_review_summary": 0, "game_features": 0,
    }
    input_rows = {"catalogue": 0, "reviews": 0, "steamspy": len(steamspy)}
    skipped = {"invalid_games": 0, "duplicate_games": 0, "invalid_reviews": 0, "duplicate_reviews": 0}
    game_ids: set[int] = set()
    attribute_counts: dict[int, dict[str, int]] = {}

    with ExitStack() as stack:
        game_writer = _open_writer(stack, output_root / "games_master.csv", GAME_FIELDS)
        bridge_writers = {
            table: _open_writer(stack, output_root / f"{table}.csv", ["steam_app_id", "value"])
            for table in GAME_BRIDGE_FIELDS.values()
        }
        with open_zip_csv(catalogue_path, CATALOGUE_MEMBER) as rows:
            for row in rows:
                input_rows["catalogue"] += 1
                game = normalise_game_row(row, steamspy)
                if game is None:
                    skipped["invalid_games"] += 1
                    continue
                app_id = game["steam_app_id"]
                if app_id in game_ids:
                    skipped["duplicate_games"] += 1
                    continue
                game_ids.add(app_id)
                game_writer.writerow(game_master_row(game))
                output_rows["games_master"] += 1
                attribute_counts[app_id] = {}
                for table, bridge_rows in build_game_bridges(game).items():
                    for bridge_row in bridge_rows:
                        bridge_writers[table].writerow(bridge_row)
                        output_rows[table] += 1
                    attribute_counts[app_id][table] = len(bridge_rows)

    summaries = ReviewSummaryAccumulator()
    review_ids: set[str] = set()
    unmatched_review_app_ids: set[int] = set()
    with (output_root / "reviews_clean.csv").open("w", encoding="utf-8", newline="") as handle:
        review_writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS, extrasaction="ignore")
        review_writer.writeheader()
        with open_zip_csv(reviews_path, REVIEWS_MEMBER) as rows:
            for row in rows:
                input_rows["reviews"] += 1
                review = normalise_review_row(row)
                if review is None:
                    skipped["invalid_reviews"] += 1
                    continue
                review_id = str(review["review_id"])
                if review_id in review_ids:
                    skipped["duplicate_reviews"] += 1
                    continue
                review_ids.add(review_id)
                if review["steam_app_id"] not in game_ids:
                    unmatched_review_app_ids.add(int(review["steam_app_id"]))
                review_writer.writerow(review)
                summaries.add(review)
                output_rows["reviews_clean"] += 1

    summary_by_game = summaries.finalize()
    with (output_root / "game_review_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        summary_writer = csv.DictWriter(handle, fieldnames=REVIEW_SUMMARY_FIELDS, extrasaction="ignore")
        summary_writer.writeheader()
        for app_id in sorted(summary_by_game):
            summary_writer.writerow(summary_by_game[app_id])
            output_rows["game_review_summary"] += 1

    with (output_root / "games_master.csv").open(encoding="utf-8", newline="") as source, (output_root / "game_features.csv").open("w", encoding="utf-8", newline="") as target:
        feature_writer = csv.DictWriter(target, fieldnames=FEATURE_FIELDS)
        feature_writer.writeheader()
        for game in csv.DictReader(source):
            app_id = int(game["steam_app_id"])
            review_summary = summary_by_game.get(app_id, {})
            counts = attribute_counts.get(app_id, {})
            feature_writer.writerow({
                "steam_app_id": app_id,
                "name": game["name"],
                "release_date": game["release_date"],
                "price_usd": game["price_usd"],
                "owners_low": game["owners_low"],
                "owners_high": game["owners_high"],
                "peak_ccu": game["peak_ccu"],
                "catalogue_review_count": game["total_reviews"],
                "catalogue_review_score": game["review_score"],
                "processed_review_count": review_summary.get("review_count", 0),
                "processed_review_score": review_summary.get("review_score"),
                "genre_count": counts.get("game_genres", 0),
                "tag_count": counts.get("game_tags", 0),
                "developer_count": counts.get("game_developers", 0),
                "publisher_count": counts.get("game_publishers", 0),
                "category_count": counts.get("game_categories", 0),
                "windows": game["windows"],
                "mac": game["mac"],
                "linux": game["linux"],
            })
            output_rows["game_features"] += 1

    report: dict[str, Any] = {
        "generated_at": _now(),
        "raw_root": str(raw_root),
        "output_root": str(output_root),
        "sources": [
            {
                "archive": str(path.relative_to(raw_root)),
                "sha256": _sha256(path),
            }
            for path in (catalogue_path, reviews_path, steamspy_path)
        ],
        "source_urls": {
            "catalogue": "https://www.kaggle.com/datasets/fronkongames/steam-games-dataset",
            "reviews": "https://www.kaggle.com/datasets/akashunikaggle/steam-game-reviews-of-743-games",
            "steamspy": "https://www.kaggle.com/datasets/muhammadaqeelkabir/steam-games-dataset-steamspy-api",
        },
        "input_rows": input_rows,
        "output_rows": output_rows,
        "skipped_rows": skipped,
        "unmatched_review_app_ids": len(unmatched_review_app_ids),
        "validations": {
            "game_ids_unique": len(game_ids) == output_rows["games_master"],
            "review_ids_unique": len(review_ids) == output_rows["reviews_clean"],
            "review_summary_reconciles": sum(
                item["review_count"] for item in summary_by_game.values()
            ) == output_rows["reviews_clean"],
            "all_required_outputs_created": True,
        },
    }
    (output_root / "data_quality_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_readme(output_root, report)
    return report


def verify_outputs(output_root: Path) -> dict[str, Any]:
    required = {
        "games_master.csv": GAME_FIELDS,
        "reviews_clean.csv": REVIEW_FIELDS,
        "game_review_summary.csv": REVIEW_SUMMARY_FIELDS,
        "game_features.csv": FEATURE_FIELDS,
    }
    for table in GAME_BRIDGE_FIELDS.values():
        required[f"{table}.csv"] = ["steam_app_id", "value"]
    missing = [name for name in required if not (output_root / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing processed outputs: {', '.join(missing)}")
    for name, expected_fields in required.items():
        with (output_root / name).open(encoding="utf-8", newline="") as handle:
            actual_fields = csv.DictReader(handle).fieldnames
        if actual_fields != expected_fields:
            raise ValueError(f"Unexpected schema in {name}: {actual_fields}")
    report_path = output_root / "data_quality_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not all(report["validations"].values()):
        raise ValueError("Data quality report contains a failed validation")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare GamePulse datasets from raw ZIP archives.")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/2026-07-30"))
    parser.add_argument("--output-root", type=Path, default=Path("data/processed/2026-08-01"))
    parser.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    if arguments.verify:
        report = verify_outputs(arguments.output_root)
    else:
        report = prepare_datasets(arguments.raw_root, arguments.output_root)
    print(json.dumps({"output_root": str(arguments.output_root), "validations": report["validations"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
