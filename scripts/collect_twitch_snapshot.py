"""Collect and persist one bounded, normalized Twitch snapshot."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamepulse.config import Settings
from gamepulse.database import ensure_twitch_game_mapping_schema, ensure_twitch_snapshot_schema
from gamepulse.game_mapping import load_game_mappings, load_steam_games, map_twitch_games, persist_game_mappings
from gamepulse.providers.twitch import GameTrend, Snapshot, StreamerObservation, TwitchProvider


@dataclass(frozen=True)
class CollectionReport:
    source_mode: str
    source_name: str
    observed_at: str
    pages_collected: int
    unique_streams: int
    categories: int
    streamers: int
    partial_coverage: bool
    game_rows_upserted: int
    streamer_rows_upserted: int


def _validate_game_trend(trend: GameTrend) -> None:
    if not str(trend.game_id).strip() or not str(trend.name).strip():
        raise ValueError("Twitch game observations require game_id and name")
    if trend.viewer_count < 0 or trend.channel_count < 0:
        raise ValueError("Twitch game counts cannot be negative")
    for value in (trend.top_one_viewer_share, trend.top_five_viewer_share):
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError("Twitch viewer concentration shares must be between 0 and 1")
    if trend.contributing_stream_rows < 0 or trend.pages_collected < 0:
        raise ValueError("Twitch coverage counts cannot be negative")


def _validate_streamer_observation(observation: StreamerObservation) -> None:
    if not str(observation.streamer_id).strip() or not str(observation.name).strip():
        raise ValueError("Twitch streamer observations require streamer_id and name")
    if observation.viewer_count < 0:
        raise ValueError("Twitch streamer viewer counts cannot be negative")


def _persist_stream_id(observation: StreamerObservation) -> str:
    return str(observation.stream_id or f"streamer:{observation.streamer_id}")


def save_game_snapshots(
    connection: sqlite3.Connection,
    snapshot: Snapshot,
    steam_app_id: int | None = None,
    steam_app_ids: dict[str, int | None] | None = None,
) -> int:
    rows = 0
    for trend in snapshot.data:
        _validate_game_trend(trend)
        mapped_app_id = (
            steam_app_ids.get(str(trend.game_id), steam_app_id)
            if steam_app_ids is not None
            else steam_app_id
        )
        connection.execute(
            """INSERT OR REPLACE INTO twitch_game_snapshots (
                observed_at, game_id, game_name, steam_app_id, rank, viewer_count, channel_count,
                viewer_to_channel, top_one_viewer_share, top_five_viewer_share, average_stream_age_seconds,
                growth_score, coverage_stream_count, coverage_page_count, partial_coverage, observed_total,
                source_mode, source_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot.observed_at,
                str(trend.game_id),
                str(trend.name),
                mapped_app_id,
                trend.rank,
                trend.viewer_count,
                trend.channel_count,
                trend.viewer_to_channel,
                trend.top_one_viewer_share,
                trend.top_five_viewer_share,
                trend.average_stream_age_seconds,
                trend.growth_score,
                trend.contributing_stream_rows,
                trend.pages_collected,
                int(bool(trend.partial_coverage)),
                int(bool(trend.observed_total)),
                snapshot.mode,
                snapshot.source_name,
            ),
        )
        rows += 1
    return rows


def save_streamer_snapshots(connection: sqlite3.Connection, snapshot: Snapshot) -> tuple[int, set[str], set[str]]:
    rows = 0
    stream_ids: set[str] = set()
    streamer_ids: set[str] = set()
    for observation in snapshot.data:
        _validate_streamer_observation(observation)
        stream_id = _persist_stream_id(observation)
        connection.execute(
            """INSERT OR REPLACE INTO twitch_streamer_snapshots (
                observed_at, stream_id, streamer_id, streamer_name, streamer_login, game_id, game_name,
                viewer_count, language, title, start_time, tags_json, channel_size_tier,
                broadcaster_type, profile_image_url, category_rank, partial_coverage, source_mode, source_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot.observed_at,
                stream_id,
                str(observation.streamer_id),
                str(observation.name),
                observation.login_name,
                str(observation.game_id),
                str(observation.game_name),
                observation.viewer_count,
                observation.language,
                observation.stream_title,
                observation.started_at,
                json.dumps(list(observation.tags), ensure_ascii=False),
                observation.channel_size_tier,
                observation.broadcaster_type,
                observation.profile_image_url,
                observation.category_rank,
                int(bool(snapshot.partial_coverage)),
                snapshot.mode,
                snapshot.source_name,
            ),
        )
        rows += 1
        stream_ids.add(stream_id)
        streamer_ids.add(str(observation.streamer_id))
    return rows, stream_ids, streamer_ids


def _provider_for(settings: Settings, demo: bool, max_pages: int | None) -> TwitchProvider:
    snapshot_path = settings.twitch_demo_snapshot if demo else settings.twitch_snapshot_path
    return TwitchProvider(
        snapshot_path,
        None if demo else settings.twitch_client_id,
        None if demo else settings.twitch_client_secret,
        max_stream_pages=max_pages if max_pages is not None else settings.twitch_max_stream_pages,
        request_timeout_seconds=settings.twitch_request_timeout_seconds,
    )


def collect_and_save(
    database_path: Path,
    settings: Settings | None = None,
    demo: bool = False,
    max_pages: int | None = None,
    provider: TwitchProvider | None = None,
) -> CollectionReport:
    """Collect one normalized snapshot and upsert it into the disposable DB."""
    if provider is None:
        project_root = Path(__file__).resolve().parents[1]
        settings = settings or Settings.from_env(project_root)
        provider = _provider_for(settings, demo, max_pages)

    collect_cycle = getattr(provider, "collect_cycle", None)
    if not callable(collect_cycle):
        raise TypeError("Twitch snapshot collection providers must implement collect_cycle()")
    game_snapshot, shared_collection = collect_cycle()
    streamer_snapshots = list(provider.get_streamers_by_game(shared_collection).values())
    game_rows = list(game_snapshot.data)
    for trend in game_rows:
        _validate_game_trend(trend)

    for streamer_snapshot in streamer_snapshots:
        for observation in streamer_snapshot.data:
            _validate_streamer_observation(observation)

    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        ensure_twitch_snapshot_schema(connection)
        ensure_twitch_game_mapping_schema(connection)
        steam_games = load_steam_games(connection)
        mappings = map_twitch_games(game_rows, steam_games)
        persist_game_mappings(connection, mappings)
        persisted_mappings = load_game_mappings(connection, [str(trend.game_id) for trend in game_rows])
        reliable_app_ids = {
            game_id: mapping.steam_app_id if mapping.is_reliable else None
            for game_id, mapping in persisted_mappings.items()
        }
        game_rows_upserted = save_game_snapshots(connection, game_snapshot, steam_app_ids=reliable_app_ids)
        streamer_rows_upserted = 0
        stream_ids: set[str] = set()
        streamer_ids: set[str] = set()
        source_modes = {game_snapshot.mode}
        for streamer_snapshot in streamer_snapshots:
            source_modes.add(streamer_snapshot.mode)
            saved_rows, saved_stream_ids, saved_streamer_ids = save_streamer_snapshots(connection, streamer_snapshot)
            streamer_rows_upserted += saved_rows
            stream_ids.update(saved_stream_ids)
            streamer_ids.update(saved_streamer_ids)
        connection.commit()
    finally:
        connection.close()

    return CollectionReport(
        source_mode=game_snapshot.mode if len(source_modes) == 1 else "Mixed",
        source_name=game_snapshot.source_name,
        observed_at=game_snapshot.observed_at,
        pages_collected=max((int(trend.pages_collected) for trend in game_rows), default=0),
        unique_streams=len(stream_ids),
        categories=len(game_rows),
        streamers=len(streamer_ids),
        partial_coverage=bool(getattr(shared_collection, "partial_coverage", False)) or any(bool(trend.partial_coverage) for trend in game_rows),
        game_rows_upserted=game_rows_upserted,
        streamer_rows_upserted=streamer_rows_upserted,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--demo", action="store_true", help="Use the local Demo fixture and never call Twitch")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum Twitch streams pages per request")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    settings = Settings.from_env(project_root)
    report = collect_and_save(args.database, settings=settings, demo=args.demo, max_pages=args.max_pages)
    print("Twitch collection report")
    print(f"Source mode: {report.source_mode}")
    print(f"Observed at: {report.observed_at}")
    print(f"Pages collected: {report.pages_collected}")
    print(f"Unique streams: {report.unique_streams}")
    print(f"Categories: {report.categories}")
    print(f"Streamers: {report.streamers}")
    print(f"Partial coverage: {'yes' if report.partial_coverage else 'no'}")


if __name__ == "__main__":
    main()
