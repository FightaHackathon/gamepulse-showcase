from __future__ import annotations

from dataclasses import dataclass

from .contracts import GameIdentity, GameSignalProvider, ProviderMetric


@dataclass(frozen=True)
class ProviderFailure:
    provider_name: str
    error: str


@dataclass(frozen=True)
class ProviderFetchReport:
    metrics: tuple[ProviderMetric, ...]
    failures: tuple[ProviderFailure, ...]


class CompositeGameSignalProvider:
    provider_name = "GamePulse composite"

    def __init__(self, providers: list[GameSignalProvider]):
        self.providers = tuple(providers)

    def fetch_with_report(self, game: GameIdentity) -> ProviderFetchReport:
        metrics: list[ProviderMetric] = []
        failures: list[ProviderFailure] = []
        for provider in self.providers:
            try:
                metrics.extend(provider.fetch(game))
            except Exception as exc:
                failures.append(
                    ProviderFailure(
                        provider_name=str(getattr(provider, "provider_name", provider.__class__.__name__)),
                        error=str(exc),
                    )
                )
        return ProviderFetchReport(tuple(metrics), tuple(failures))

    def fetch(self, game: GameIdentity) -> list[ProviderMetric]:
        return list(self.fetch_with_report(game).metrics)
