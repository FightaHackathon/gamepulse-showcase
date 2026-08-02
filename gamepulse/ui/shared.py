"""Pure shared state and small rendering helpers."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class DemoState:
    selected_app_id: int
    steam_profile: str | None = None


def select_game(state: DemoState, steam_app_id: int) -> DemoState:
    return replace(state, selected_app_id=int(steam_app_id))


def source_badge(source_mode: str, observed_at: str | None = None) -> str:
    if observed_at:
        return f"{source_mode} · observed {observed_at}"
    return source_mode


def render_game_header(st, game, source_mode: str = "Local prepared data") -> None:
    st.subheader(game.name)
    details = []
    if game.release_date:
        details.append(f"Released {game.release_date}")
    if game.price_usd is not None:
        details.append("Free" if game.price_usd == 0 else f"${game.price_usd:.2f}")
    if game.review_score is not None:
        details.append(f"Review score {game.review_score:.1%}")
    st.caption(" · ".join(details) + f" · Source: {source_mode}")
