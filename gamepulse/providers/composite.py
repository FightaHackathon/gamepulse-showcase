"""Provider routing and merging for GamePulse's source-neutral signal layer."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from gamepulse.providers.contracts import CreatorSignal, GameSignal, SignalSnapshot
from gamepulse.providers.creator_directory import CreatorDirectoryProvider
from gamepulse.providers.snapshot import ImportedSignals, load_snapshot
from gamepulse.providers.steam_signals import SteamPublicGameSignalProvider


def _legacy_twitch_game(item, snapshot) -> GameSignal:
    viewers = getattr(item, "viewer_count", None)
    channels = getattr(item, "channel_count", None)
    return GameSignal(
        game_id=str(getattr(item, "game_id", "")),
        name=str(getattr(item, "name", "")),
        audience_value=(None if viewers is None else float(viewers)),
        audience_metric="twitch_viewers" if viewers is not None else None,
        competition_value=(None if channels is None else float(channels)),
        competition_metric="twitch_live_channels" if channels is not None else None,
        growth_score=(None if getattr(item, "growth_score", None) is None else float(item.growth_score)),
        tags=tuple(getattr(item, "tags", ()) or ()),
        platform="Twitch",
        source_name=str(snapshot.source_name),
        observed_at=str(snapshot.observed_at),
        confidence="live" if str(snapshot.mode).casefold() == "live" else "demo",
        source_mode=str(snapshot.mode),
    )


def _legacy_twitch_creator(item, snapshot) -> CreatorSignal:
    viewers = getattr(item, "viewer_count", None)
    return CreatorSignal(
        creator_id=str(getattr(item, "streamer_id", getattr(item, "creator_id", ""))),
        name=str(getattr(item, "name", "")),
        platform="Twitch",
        profile_url=getattr(item, "profile_url", None),
        game_id=(str(getattr(item, "game_id", "")) or None),
        game_name=(str(getattr(item, "game_name", "")) or None),
        audience_value=(None if viewers is None else float(viewers)),
        audience_metric="twitch_viewers" if viewers is not None else None,
        language=str(getattr(item, "language", "") or ""),
        channel_size_tier=str(getattr(item, "channel_size_tier", "unknown") or "unknown"),
        tags=tuple(getattr(item, "tags", ()) or ()),
        games=((str(getattr(item, "game_name")),) if getattr(item, "game_name", None) else ()),
        observed_at=str(snapshot.observed_at),
        source_name=str(snapshot.source_name),
        confidence="live" if str(snapshot.mode).casefold() == "live" else "demo",
        source_mode=str(snapshot.mode),
    )


class CompositeSignalProvider:
    """Choose legitimate game sources and merge creator sources with provenance."""

    def __init__(
        self,
        *,
        database_path: Path,
        creator_directory_path: Path,
        snapshot_path: Path | None = None,
        twitch_provider=None,
        game_provider_mode: str = "auto",
        creator_provider_mode: str = "auto",
    ):
        self.steam = SteamPublicGameSignalProvider(database_path)
        self.creator_directory = CreatorDirectoryProvider(creator_directory_path)
        self.snapshot_path = Path(snapshot_path) if snapshot_path else None
        self.twitch_provider = twitch_provider
        self.game_provider_mode = str(game_provider_mode or "auto").casefold()
        self.creator_provider_mode = str(creator_provider_mode or "auto").casefold()

    def _imported(self) -> ImportedSignals | None:
        if self.snapshot_path is None or not self.snapshot_path.exists():
            return None
        try:
            return load_snapshot(self.snapshot_path)
        except (OSError, ValueError):
            return None

    def _twitch_games(self) -> SignalSnapshot[GameSignal] | None:
        if self.twitch_provider is None:
            return None
        snapshot = self.twitch_provider.get_game_trends()
        data = [
            item if isinstance(item, GameSignal) else _legacy_twitch_game(item, snapshot)
            for item in snapshot.data
        ]
        return SignalSnapshot(
            str(snapshot.mode),
            str(snapshot.observed_at),
            str(snapshot.source_name),
            data,
            "live" if str(snapshot.mode).casefold() == "live" else "fallback",
        )

    def get_game_trends(self) -> SignalSnapshot[GameSignal]:
        """Return one coherent metric family instead of silently mixing unlike units."""

        if self.game_provider_mode == "twitch":
            twitch = self._twitch_games()
            if twitch is not None and twitch.data:
                return twitch
        if self.game_provider_mode in {"snapshot", "imported"}:
            imported = self._imported()
            if imported is not None and imported.games.data:
                return imported.games

        steam = self.steam.get_game_trends()
        if steam.data:
            return steam

        imported = self._imported()
        if imported is not None and imported.games.data:
            return imported.games

        twitch = self._twitch_games()
        if twitch is not None and twitch.data:
            return twitch

        return SignalSnapshot(
            "Unavailable",
            "",
            "No game signal provider available",
            [],
            "unavailable",
        )

    def _twitch_creators(
        self,
        game_id: str | None,
        game_name: str | None,
    ) -> list[CreatorSignal]:
        if self.twitch_provider is None:
            return []
        try:
            if hasattr(self.twitch_provider, "get_creators"):
                snapshot = self.twitch_provider.get_creators(
                    game_id=game_id,
                    game_name=game_name,
                )
            elif game_id is not None:
                snapshot = self.twitch_provider.get_streamers(str(game_id))
            else:
                return []
        except (OSError, RuntimeError, ValueError, KeyError):
            return []
        return [
            item if isinstance(item, CreatorSignal) else _legacy_twitch_creator(item, snapshot)
            for item in snapshot.data
        ]

    def _imported_creators(
        self,
        game_id: str | None,
        game_name: str | None,
    ) -> list[CreatorSignal]:
        imported = self._imported()
        if imported is None:
            return []

        target_game_id = str(game_id) if game_id is not None else None
        target_name = str(game_name or "").casefold()
        creators: list[CreatorSignal] = []
        for creator in imported.creators.data:
            if target_game_id and creator.game_id not in {None, "", target_game_id}:
                continue
            if target_name:
                known_names = {name.casefold() for name in creator.games}
                if creator.game_name:
                    known_names.add(creator.game_name.casefold())
                if known_names and target_name not in known_names:
                    continue
            creators.append(creator)
        return creators

    @staticmethod
    def _dedupe_creators(creators: Iterable[CreatorSignal]) -> list[CreatorSignal]:
        output: dict[tuple[str, str], CreatorSignal] = {}
        priority = {
            "live": 4,
            "creator submitted": 3,
            "imported": 2,
            "manual": 1,
            "demo": 0,
        }
        for creator in creators:
            key = (creator.platform.casefold(), creator.creator_id.casefold())
            existing = output.get(key)
            if existing is None or priority.get(
                creator.source_mode.casefold(), 1
            ) > priority.get(existing.source_mode.casefold(), 1):
                output[key] = creator
        return sorted(
            output.values(),
            key=lambda item: (item.name.casefold(), item.creator_id),
        )

    def get_creators(
        self,
        game_id: str | None = None,
        game_name: str | None = None,
    ) -> SignalSnapshot[CreatorSignal]:
        """Return creators from the explicitly selected source, or merge them in auto mode."""

        mode = self.creator_provider_mode
        if mode == "twitch":
            creators = self._twitch_creators(game_id, game_name)
        elif mode in {"snapshot", "imported"}:
            creators = self._imported_creators(game_id, game_name)
        elif mode == "directory":
            creators = list(
                self.creator_directory.get_creators(game_id, game_name).data
            )
        else:
            # Auto is the only creator mode that merges sources.
            creators = list(
                self.creator_directory.get_creators(game_id, game_name).data
            )
            creators.extend(self._imported_creators(game_id, game_name))
            creators.extend(self._twitch_creators(game_id, game_name))

        creators = self._dedupe_creators(creators)
        observed_at = max(
            (creator.observed_at for creator in creators if creator.observed_at),
            default="",
        )
        modes = {creator.source_mode for creator in creators}
        snapshot_mode = (
            next(iter(modes))
            if len(modes) == 1
            else "Mixed"
            if modes
            else "Unavailable"
        )
        confidence = "mixed" if len(modes) > 1 else "provider"
        return SignalSnapshot(
            snapshot_mode,
            observed_at,
            "Composite creator sources",
            creators,
            confidence,
        )
