import gzip
import json

from gamepulse.trend_artifact import load_trend_artifact


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
