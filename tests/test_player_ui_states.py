import unittest
from pathlib import Path
from types import SimpleNamespace

from gamepulse.catalog import PreferenceOptions
from gamepulse.player_session import PlayerProfileSession, empty_profile_session
from gamepulse.recommendations import PlayerPreferences, Recommendation
from gamepulse.ui.player_components import render_personalization, render_recommendation_card, render_recommendation_empty_state


class _Form:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakeStreamlit:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.successes = []
        self.captions = []
        self.markdowns = []
        self.buttons = []
        self.form_submit_kwargs = []

    def subheader(self, value):
        self.subheader_value = value

    def info(self, value):
        self.infos.append(value)

    def warning(self, value):
        self.warnings.append(value)

    def success(self, value):
        self.successes.append(value)

    def caption(self, value):
        self.captions.append(value)

    def form(self, *_args, **_kwargs):
        return _Form()

    def text_input(self, _label, value="", **_kwargs):
        return value

    def form_submit_button(self, *_args, **_kwargs):
        self.form_submit_kwargs.append(_kwargs)
        return False

    def button(self, label, **_kwargs):
        self.buttons.append(label)
        return False

    def markdown(self, value, **_kwargs):
        self.markdowns.append(value)


class PlayerModeStateTests(unittest.TestCase):
    def _settings(self, enabled):
        return SimpleNamespace(steam_enabled=enabled)

    def test_missing_key_keeps_manual_mode_ready(self):
        fake = _FakeStreamlit()

        render_personalization(fake, empty_profile_session(), self._settings(False), PreferenceOptions(("RPG",), ("Action",)))

        self.assertIn("public-profile analysis is ready", " ".join(fake.infos))
        self.assertIn("STEAM_WEB_API_KEY", " ".join(fake.captions))
        self.assertFalse(fake.form_submit_kwargs[0].get("disabled", False))

    def test_private_and_rate_limited_copy_is_safe(self):
        for status, message in (("private", "Game Details are private."), ("rate_limited", "Steam is temporarily rate limited.")):
            fake = _FakeStreamlit()
            state = PlayerProfileSession(status=status, profile_input="profile", message=message)

            render_personalization(fake, state, self._settings(True), PreferenceOptions((), ()))

            self.assertEqual(fake.warnings, [message])
            self.assertNotIn("api_key", " ".join(fake.warnings).casefold())

    def test_empty_state_and_missing_artwork_have_recovery_copy(self):
        fake = _FakeStreamlit()
        render_recommendation_empty_state(fake, PlayerPreferences(discovery_mode="hidden_gems"))
        self.assertIn("No games match all active filters.", fake.infos)
        self.assertIn("broaden", " ".join(fake.captions).casefold())

        render_recommendation_card(
            fake,
            Recommendation(
                app_id=10,
                name="No Art Game",
                match_score=72,
                score_band="Strong match",
                reasons=("matches your selected preferences",),
                price_usd=0.0,
                review_score=0.9,
                steam_store_url="https://store.steampowered.com/app/10",
            ),
        )
        self.assertIn("gp-game-art-placeholder", fake.markdowns[-1])
        self.assertIn("Artwork unavailable", fake.markdowns[-1])

    def test_connected_state_shows_count_and_inferred_chips(self):
        fake = _FakeStreamlit()
        state = PlayerProfileSession(
            status="connected",
            profile_input="profile",
            owned_app_ids=frozenset({1, 2}),
            preferences=PlayerPreferences(preferred_tags=("rpg",), preferred_genres=("action",)),
        )

        render_personalization(fake, state, self._settings(True), PreferenceOptions((), ()))

        self.assertIn("2 public library games", fake.successes[0])
        self.assertIn("Inferred preferences", " ".join(fake.captions))
        self.assertEqual(fake.buttons, ["Refresh library", "Clear Steam connection"])


if __name__ == "__main__":
    unittest.main()
