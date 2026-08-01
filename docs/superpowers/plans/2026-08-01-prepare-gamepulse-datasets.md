# GamePulse Prepared Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the three downloaded Steam archives into documented, validated CSV datasets that the local GamePulse prototype can load directly.

**Architecture:** Read source CSV files directly from their ZIP archives so `data/raw` remains immutable. Treat the Fronkon Games catalogue as the canonical game source, use the SteamSpy dataset only as a metric fallback, and emit a narrow game master, bridge tables for multi-value attributes, cleaned reviews, per-game review summaries, and dashboard-ready game features under a date-stamped `data/processed` directory.

**Tech Stack:** Python 3 and standard library (`csv`, `zipfile`, `hashlib`, `json`, `datetime`, `unittest`).

## Global Constraints

- Do not modify or extract files in `data/raw/2026-07-30`.
- Write generated output only under `data/processed/2026-08-01`.
- Use `AppID`/`appid` as an integer Steam identifier and never join datasets by game name.
- Preserve raw review text but do not apply language classification in this preparation pass.
- Record all source paths, row counts, validations, transformation date, and failures in `data_quality_report.json`.
- Do not create a git commit unless the user explicitly requests one.

---

### Task 1: Source access and reusable parsing utilities

**Files:**
- Create: `gamepulse_data/__init__.py`
- Create: `gamepulse_data/source_io.py`
- Create: `tests/test_source_io.py`

**Interfaces:**
- Consumes: ZIP archives under `data/raw/2026-07-30`.
- Produces: `open_zip_csv(archive_path: Path, member_name: str) -> Iterator[dict[str, str]]` and `parse_delimited_values(value: str) -> list[str]`.

- [ ] **Step 1: Write the failing source-reading test**

```python
from pathlib import Path

from gamepulse_data.source_io import open_zip_csv, parse_delimited_values


def test_parse_delimited_values_removes_empty_duplicate_values():
    assert parse_delimited_values("Action, RPG,Action, ") == ["Action", "RPG"]


def test_open_zip_csv_reads_named_member(tmp_path: Path):
    # The test creates a small ZIP fixture containing games.csv.
    rows = list(open_zip_csv(tmp_path / "games.zip", "games.csv"))
    assert rows == [{"AppID": "10", "Name": "Example"}]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_source_io -v`

Expected: FAIL because `gamepulse_data.source_io` does not exist.

- [ ] **Step 3: Implement safe ZIP CSV reading and list parsing**

```python
def open_zip_csv(archive_path: Path, member_name: str):
    with ZipFile(archive_path) as archive:
        with archive.open(member_name) as binary_file:
            yield from csv.DictReader(TextIOWrapper(binary_file, encoding="utf-8"))


def parse_delimited_values(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.test_source_io -v`

Expected: PASS.

### Task 2: Game master and bridge-table preparation

**Files:**
- Create: `gamepulse_data/games.py`
- Create: `tests/test_games.py`

**Interfaces:**
- Consumes: canonical Fronkon `games.csv` rows and SteamSpy `steam_games_dataset.csv` rows.
- Produces: `normalise_game_row(row: dict[str, str], steamspy: dict[int, dict[str, str]]) -> dict[str, object]` and `build_game_bridges(game: dict[str, object]) -> dict[str, list[dict[str, object]]]`.

- [ ] **Step 1: Write the failing normalization tests**

```python
from gamepulse_data.games import normalise_game_row


def test_normalise_game_row_parses_owner_range_and_review_score():
    game = normalise_game_row(
        {"AppID": "10", "Name": "Example", "Estimated owners": "20,000 - 50,000",
         "Positive": "90", "Negative": "10", "Price": "12.5"},
        {},
    )
    assert game["steam_app_id"] == 10
    assert game["owners_low"] == 20000
    assert game["owners_high"] == 50000
    assert game["review_score"] == 0.9
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_games -v`

Expected: FAIL because `gamepulse_data.games` does not exist.

- [ ] **Step 3: Implement game normalization**

Normalize dates, booleans, numeric metrics, owner ranges, platform flags, and review metrics. Retain only fields required by discovery, comparison, recommendations, and later Twitch enrichment. Prefer canonical catalogue values; use SteamSpy values only when catalogue metrics are missing.

- [ ] **Step 4: Implement bridge generation**

Generate unique rows with `steam_app_id` and one value for each of `genres`, `tags`, `developers`, `publishers`, and `categories`. Do not preserve comma-separated lists in the bridge outputs.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest tests.test_games -v`

Expected: PASS.

### Task 3: Review cleaning and game-level summaries

**Files:**
- Create: `gamepulse_data/reviews.py`
- Create: `tests/test_reviews.py`

**Interfaces:**
- Consumes: `steam_game_reviews_730945.csv` rows.
- Produces: `normalise_review_row(row: dict[str, str]) -> dict[str, object] | None` and `summarise_reviews(rows: Iterable[dict[str, object]]) -> dict[int, dict[str, object]]`.

- [ ] **Step 1: Write the failing review tests**

```python
from gamepulse_data.reviews import normalise_review_row, summarise_reviews


def test_normalise_review_row_drops_empty_text_and_creates_stable_id():
    assert normalise_review_row({"appid": "10", "review": "  "}) is None
    review = normalise_review_row({"appid": "10", "review": "Great game", "voted_up": "True"})
    assert review["steam_app_id"] == 10
    assert review["review_id"]
    assert review["recommended"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_reviews -v`

Expected: FAIL because `gamepulse_data.reviews` does not exist.

- [ ] **Step 3: Implement review normalization**

Keep stable review IDs, app IDs, normalized text, recommendation flag, word count, votes, created timestamp, playtime, game name, price, and release date. Drop rows without an app ID or non-empty review text. Remove duplicates using the generated review ID.

- [ ] **Step 4: Implement summaries**

For every game, emit review count, recommended count, not-recommended count, review score, median word count, median playtime, helpful-vote total, and latest review timestamp.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest tests.test_reviews -v`

Expected: PASS.

### Task 4: Reproducible preparation command and output documentation

**Files:**
- Create: `scripts/prepare_datasets.py`
- Create: `data/processed/2026-08-01/README.md`
- Create: `tests/test_prepare_datasets.py`

**Interfaces:**
- Consumes: functions from `gamepulse_data.source_io`, `gamepulse_data.games`, and `gamepulse_data.reviews`.
- Produces: `games_master.csv`, five bridge CSVs, `reviews_clean.csv`, `game_review_summary.csv`, `game_features.csv`, and `data_quality_report.json`.

- [ ] **Step 1: Write the failing end-to-end fixture test**

```python
from scripts.prepare_datasets import prepare_datasets


def test_prepare_datasets_writes_all_required_outputs(tmp_path):
    report = prepare_datasets(raw_root=tmp_path / "raw", output_root=tmp_path / "processed")
    assert (tmp_path / "processed" / "games_master.csv").exists()
    assert (tmp_path / "processed" / "reviews_clean.csv").exists()
    assert report["validations"]["game_ids_unique"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_prepare_datasets -v`

Expected: FAIL because `scripts.prepare_datasets` does not exist.

- [ ] **Step 3: Implement a streaming preparation command**

Read the large CSVs directly from ZIP archives and write output incrementally with `csv.DictWriter`; do not load the catalogue or reviews entirely into memory. Merge SteamSpy fallback metrics by app ID. Derive `game_features.csv` by joining game master and review summaries.

- [ ] **Step 4: Add data quality report and README**

The JSON report must contain source archive hashes, input/output row counts, duplicates removed, null counts for key fields, unmatched review app IDs, and validation booleans. The README must document every output file, primary key, refresh rule, and limitations.

- [ ] **Step 5: Run fixture test and full command**

Run: `python -m unittest tests.test_prepare_datasets -v`

Expected: PASS.

Run: `python scripts/prepare_datasets.py --raw-root data/raw/2026-07-30 --output-root data/processed/2026-08-01`

Expected: all required outputs and a quality report are created.

### Task 5: Full-data validation and handoff

**Files:**
- Modify: `data/processed/2026-08-01/data_quality_report.json`
- Modify: `data/processed/2026-08-01/README.md`

**Interfaces:**
- Consumes: completed processed CSV files.
- Produces: verified outputs ready for the Streamlit prototype.

- [ ] **Step 1: Verify row counts and identifiers**

Run: `python -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 2: Verify processed CSV headers and key counts**

Run: `python scripts/prepare_datasets.py --verify --output-root data/processed/2026-08-01`

Expected: `game_ids_unique`, `review_ids_unique`, and `review_summary_reconciles` all report `true`.

- [ ] **Step 3: Verify files are usable without raw extraction**

Open `games_master.csv`, `game_features.csv`, and `game_review_summary.csv` with `csv.DictReader` and confirm that their expected headers are present.

- [ ] **Step 4: Update the README with the actual generated counts**

Record the exact counts from the final quality report and state that Twitch/IGDB data remains a live or separately collected source.
