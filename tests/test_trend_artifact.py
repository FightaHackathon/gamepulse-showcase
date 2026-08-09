import gzip
import json

from gamepulse.trend_artifact import ARTIFACT_PATH, load_peak_ccu_artifact, load_trend_artifact


def test_bundled_trend_artifact_has_expected_identity_and_rows():
    rows = load_trend_artifact()

    assert ARTIFACT_PATH.is_file()
    assert len(rows) == 251_712
    row = rows[(10, "developer")]
    assert row.source_name == "GamePulse Full Catalog Import"
    assert row.source_mode == "derived_multi_signal"
    assert row.components["signals_available"] is True


def test_trend_artifact_loads_compact_rows(tmp_path):
    path = tmp_path / "trends.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(
            [
                {
                    "steam_app_id": 10,
                    "audience": "developer",
                    "score": 82.5,
                    "components": {"genre_demand": 70},
                    "observed_at": "2026-08-01T18:32:17+00:00",
                    "source_name": "GamePulse Full Catalog Import",
                    "source_mode": "derived_multi_signal",
                    "confidence": "medium",
                }
            ],
            handle,
        )

    row = load_trend_artifact(str(path))[(10, "developer")]
    assert row.score == 82.5
    assert row.components == {"genre_demand": 70}
    assert row.source_name == "GamePulse Full Catalog Import"


def test_peak_artifact_loader_returns_only_player_peak_values(tmp_path):
    path = tmp_path / "trends.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(
            [
                {"steam_app_id": 10, "audience": "player", "components": {"peak_ccu": 42}},
                {"steam_app_id": 10, "audience": "developer", "components": {"peak_ccu": 99}},
                {"steam_app_id": 20, "audience": "player", "components": {"peak_ccu": 0}},
            ],
            handle,
        )

    assert load_peak_ccu_artifact(str(path)) == {10: 42, 20: 0}
