"""Optional compact trend-score artifact used when Neon has no trend rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ARTIFACT_PATH = Path(__file__).with_name("assets") / "trend_scores.json.gz"


@dataclass(frozen=True)
class TrendArtifactRow:
    steam_app_id: int
    audience: str
    score: float
    components: dict[str, Any]
    observed_at: datetime
    source_name: str
    source_mode: str
    confidence: str


@lru_cache(maxsize=1)
def load_trend_artifact(path: str = str(ARTIFACT_PATH)) -> dict[tuple[int, str], TrendArtifactRow]:
    artifact = Path(path)
    if not artifact.is_file():
        return {}
    with gzip.open(artifact, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows: dict[tuple[int, str], TrendArtifactRow] = {}
    for item in payload:
        observed_at = datetime.fromisoformat(str(item["observed_at"]).replace("Z", "+00:00"))
        row = TrendArtifactRow(
            steam_app_id=int(item["steam_app_id"]),
            audience=str(item["audience"]),
            score=float(item["score"]),
            components=dict(item.get("components") or {}),
            observed_at=observed_at,
            source_name=str(item["source_name"]),
            source_mode=str(item["source_mode"]),
            confidence=str(item["confidence"]),
        )
        rows[(row.steam_app_id, row.audience)] = row
    return rows
