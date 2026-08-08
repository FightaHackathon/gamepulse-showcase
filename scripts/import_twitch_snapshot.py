"""Import an authorized/manual Twitch JSON export for local prototype use."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamepulse.providers.twitch_snapshot import import_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Authorized JSON export; never a twitch.tv HTML page")
    parser.add_argument("--output", type=Path, default=Path("data/manual/twitch_snapshot.json"))
    args = parser.parse_args()
    import_snapshot(args.input, args.output)
    print(f"Imported authorized Twitch snapshot to {args.output}")


if __name__ == "__main__":
    main()
