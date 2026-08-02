import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from gamepulse.streamer_fit import PromotionCampaignProfile, rank_streamers
from gamepulse.ui.developer import _profile_from_records
from gamepulse.ui.developer_components import creator_fits_csv, render_creator_fit_card


class _FakeStreamlit:
    def __init__(self):
        self.markdowns = []

    def markdown(self, value, unsafe_allow_html=False):
        self.markdowns.append(value)


def _record(
    mode: str,
    source_name: str,
    observed_at: str,
    game_name: str = "Target Game",
    partial_coverage: bool = False,
    collection_id: str | None = None,
) -> dict[str, object]:
    return {
        "observed_at": observed_at,
        "stream_id": f"stream-{observed_at}-{game_name}",
        "streamer_id": "creator-1",
        "streamer_name": "Creator One",
        "streamer_login": "creator_one",
        "game_id": game_name.casefold().replace(" ", "-"),
        "game_name": game_name,
        "viewer_count": 1000,
        "language": "en",
        "tags": ("action",),
        "channel_size_tier": "emerging",
        "source_mode": mode,
        "source_name": source_name,
        "partial_coverage": partial_coverage,
        "collection_id": collection_id or f"{mode}:{observed_at}",
    }


class DeveloperProvenanceTests(unittest.TestCase):
    def test_live_target_and_fallback_similar_records_are_not_labelled_live(self):
        profile = _profile_from_records(
            "creator-1",
            [
                _record("Live", "Twitch target collection", "2026-08-01T12:00:00Z"),
                _record("Fallback", "Cached similar fallback", "2026-07-31T12:00:00Z", "Similar Game", True),
            ],
            "Target Game",
            ("Similar Game",),
        )

        self.assertEqual(profile.source_mode, "Mixed")
        self.assertNotEqual(profile.source_mode, "Live")
        self.assertEqual(profile.observed_at, "2026-08-01T12:00:00Z")
        self.assertTrue(profile.partial_coverage)
        self.assertIn("Fallback", profile.provenance_note)
        self.assertEqual(len(profile.collection_ids), 2)

    def test_stale_history_uses_its_timestamp_and_lowers_confidence(self):
        profile = _profile_from_records(
            "creator-1",
            [_record("Cached/Snapshot", "database history", "2025-01-01T00:00:00Z")],
            "Target Game",
            (),
        )
        fit = rank_streamers(
            PromotionCampaignProfile("Target Game"),
            [profile],
            now=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )[0]

        self.assertEqual(profile.observed_at, "2025-01-01T00:00:00Z")
        self.assertLess(fit.confidence_score, 0.5)
        self.assertTrue(any("stale" in caution.casefold() for caution in fit.cautions))

    def test_fresh_live_record_wins_timestamp_over_older_live_history(self):
        profile = _profile_from_records(
            "creator-1",
            [
                _record("Live", "older live history", "2025-01-01T00:00:00Z"),
                _record("Live", "current live collection", "2026-08-01T12:00:00Z"),
            ],
            "Target Game",
            (),
        )

        self.assertEqual(profile.source_mode, "Live")
        self.assertEqual(profile.observed_at, "2026-08-01T12:00:00Z")
        self.assertEqual(profile.source_name, "current live collection")

    def test_mixed_and_fallback_source_quality_reduce_confidence_below_live(self):
        live = _profile_from_records(
            "live",
            [_record("Live", "live collection", "2026-08-01T12:00:00Z")],
            "Target Game",
            (),
        )
        mixed = _profile_from_records(
            "mixed",
            [
                _record("Live", "live collection", "2026-08-01T12:00:00Z"),
                _record("Fallback", "fallback collection", "2026-07-31T12:00:00Z"),
            ],
            "Target Game",
            (),
        )
        fallback = _profile_from_records(
            "fallback",
            [_record("Fallback", "fallback collection", "2026-08-01T12:00:00Z")],
            "Target Game",
            (),
        )
        fits = rank_streamers(
            PromotionCampaignProfile("Target Game"),
            [live, mixed, fallback],
            now=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )
        confidence = {fit.streamer_id: fit.confidence_score for fit in fits}

        self.assertGreater(confidence["live"], confidence["mixed"])
        self.assertGreater(confidence["mixed"], confidence["fallback"])

    def test_card_and_csv_use_the_same_derived_provenance(self):
        profile = _profile_from_records(
            "creator-1",
            [_record("Mixed", "Live + cached history", "2026-08-01T12:00:00Z", partial_coverage=True)],
            "Target Game",
            (),
        )
        fit = rank_streamers(PromotionCampaignProfile("Target Game"), [profile])[0]
        st = _FakeStreamlit()

        render_creator_fit_card(st, fit)
        csv_text = creator_fits_csv([fit])

        self.assertIn("Source: Mixed", st.markdowns[-1])
        self.assertIn("2026-08-01T12:00:00Z", st.markdowns[-1])
        self.assertIn("Mixed", csv_text)
        self.assertIn("2026-08-01T12:00:00Z", csv_text)
        self.assertIn("Live + cached history", csv_text)


if __name__ == "__main__":
    unittest.main()
