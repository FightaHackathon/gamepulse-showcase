import unittest

from gamepulse.streamer_fit import (
    PromotionCampaignProfile,
    StreamerProfile,
    classify_creator_tier,
    rank_streamers,
)
from gamepulse.ui.developer import _profile_from_records, filter_creator_fits_by_tier


def _record(
    viewer_count: int | None,
    *,
    source_mode: str = "Live",
    channel_size_tier: str = "unknown",
    observed_at: str = "2026-08-01T12:00:00Z",
) -> dict[str, object]:
    return {
        "observed_at": observed_at,
        "stream_id": f"stream-{observed_at}",
        "streamer_id": "creator-1",
        "streamer_name": "Creator One",
        "streamer_login": "creator_one",
        "game_id": "target",
        "game_name": "Target Game",
        "viewer_count": viewer_count,
        "language": "en",
        "tags": ("action",),
        "channel_size_tier": channel_size_tier,
        "source_mode": source_mode,
        "source_name": "Twitch",
        "collection_id": f"{source_mode}:{observed_at}",
    }


class CreatorTierTests(unittest.TestCase):
    def test_boundary_values_map_to_directional_audience_bands(self):
        cases = (
            (None, "unknown"),
            (0, "unknown"),
            (99, "unknown"),
            (100, "emerging"),
            (999, "emerging"),
            (1_000, "mid-size"),
            (4_999, "mid-size"),
            (5_000, "large"),
            (100_000, "large"),
        )

        for viewers, expected in cases:
            with self.subTest(viewers=viewers):
                self.assertEqual(classify_creator_tier(viewers), expected)

    def test_enough_history_uses_median_viewers(self):
        self.assertEqual(
            classify_creator_tier(100, observation_count=3, history=(100, 1_500, 5_000)),
            "mid-size",
        )

    def test_live_observation_without_tier_is_derived_for_profile(self):
        profile = _profile_from_records(
            "creator-1",
            [_record(2_500)],
            "Target Game",
            (),
        )

        self.assertEqual(profile.tier, "mid-size")

    def test_direct_profile_with_unknown_tier_is_derived_for_scoring(self):
        profile = StreamerProfile("creator-1", {"Target Game"}, "en", "unknown", 2_500)

        self.assertEqual(profile.tier, "mid-size")

    def test_demo_and_live_use_the_same_audience_tier(self):
        profile = _profile_from_records(
            "creator-1",
            [_record(5_000, source_mode="Demo", channel_size_tier="emerging")],
            "Target Game",
            (),
        )

        self.assertEqual(profile.tier, "large")

        live_profile = _profile_from_records(
            "creator-1",
            [_record(5_000, source_mode="Live", channel_size_tier="unknown")],
            "Target Game",
            (),
        )

        self.assertEqual(live_profile.tier, "large")
        fits = rank_streamers(PromotionCampaignProfile("Target Game"), [profile, live_profile])
        selected = filter_creator_fits_by_tier(fits, ("large",))
        self.assertEqual(len(selected), 2)

    def test_unknown_audience_does_not_drop_creator_from_unfiltered_ranking(self):
        profile = _profile_from_records(
            "creator-1",
            [_record(None, source_mode="Demo", channel_size_tier="emerging")],
            "Target Game",
            (),
        )

        self.assertEqual(profile.tier, "unknown")
        fits = rank_streamers(PromotionCampaignProfile("Target Game"), [profile])
        self.assertEqual([fit.streamer_id for fit in fits], ["creator-1"])

    def test_persisted_history_without_tier_uses_median_viewers(self):
        profile = _profile_from_records(
            "creator-1",
            [
                _record(100, source_mode="Cached/Snapshot", observed_at="2026-07-30T12:00:00Z"),
                _record(5_000, source_mode="Cached/Snapshot", observed_at="2026-07-31T12:00:00Z"),
                _record(1_000, source_mode="Cached/Snapshot", observed_at="2026-08-01T12:00:00Z"),
            ],
            "Target Game",
            (),
        )

        self.assertEqual(profile.tier, "mid-size")

    def test_invalid_explicit_demo_tier_is_replaced_by_derived_tier(self):
        profile = _profile_from_records(
            "creator-1",
            [_record(2_500, source_mode="Demo", channel_size_tier="not-a-tier")],
            "Target Game",
            (),
        )

        self.assertEqual(profile.tier, "mid-size")

    def test_preferred_tier_filter_keeps_matching_live_creator(self):
        profile = _profile_from_records(
            "creator-1",
            [_record(2_500)],
            "Target Game",
            (),
        )
        fit = rank_streamers(PromotionCampaignProfile("Target Game"), [profile])[0]

        selected = filter_creator_fits_by_tier([fit], ("mid-size",))

        self.assertEqual([item.streamer_id for item in selected], ["creator-1"])

    def test_missing_viewers_stay_unknown_and_do_not_match(self):
        for viewer_count in (None, 0):
            with self.subTest(viewer_count=viewer_count):
                profile = _profile_from_records(
                    "creator-1",
                    [_record(viewer_count)],
                    "Target Game",
                    (),
                )
                fit = rank_streamers(PromotionCampaignProfile("Target Game"), [profile])[0]

                self.assertEqual(profile.tier, "unknown")
                self.assertEqual(filter_creator_fits_by_tier([fit], ("emerging",)), [])


if __name__ == "__main__":
    unittest.main()
