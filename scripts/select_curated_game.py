"""Print deterministic curated-game candidates for the prototype demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamepulse.catalog import Catalog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--write-config", type=Path)
    args = parser.parse_args()
    candidates = Catalog(args.database).rank_demo_candidates(args.limit)
    for game in candidates:
        print(f"{game.steam_app_id}\t{game.name}\treviews={game.total_reviews}\towners={game.owners_low}-{game.owners_high}")
    if args.write_config and candidates:
        args.write_config.parent.mkdir(parents=True, exist_ok=True)
        args.write_config.write_text(json.dumps({"selected_app_id": candidates[0].steam_app_id, "selection_reason": "complete metadata, review coverage, and public market fields"}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
