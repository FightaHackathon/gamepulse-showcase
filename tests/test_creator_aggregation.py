import unittest

from gamepulse.creator_aggregation import aggregate_creator_categories
from gamepulse.ui.developer import _profile_from_records


def _record(category: str, index: int, *, source_mode: str = "Live") -> dict[str, object]:
    return {
        "observed_at": f"2026-08-01T00:{index:02d}:00Z",
        "stream_id": f"stream-{index}",
        "streamer_id": "creator-1",
        "streamer_name": "Creator One",
        "streamer_login": "creator_one",
        "game_id": category.casefold().replace(" ", "-"),
        "game_name": category,
        "viewer_count": 1_000 + index,
        "language": "en",
        "tags": ("action",),
        "channel_size_tier": "mid-size",
        "source_mode": source_mode,
        "source_name": "Twitch",
        "collection_id": f"{source_mode}:collection-{index}",
    }


class CreatorAggregationTests(unittest.TestCase):
    def test_primary_share_uses_all_category_observations(self):
        records = [_record("Counter-Strike", index) for index in range(20)]
        records.append(_record("PUBG", 20))

        profile = _profile_from_records("creator-1", records, "Counter-Strike", ())

        self.assertEqual(profile.primary_category, "Counter-Strike")
        self.assertAlmostEqual(profile.primary_category_share, 20 / 21)

    def test_exact_provider_and_database_duplicate_is_counted_once(self):
        provider = _record("Counter-Strike", 0, source_mode="Live")
        database = dict(provider)
        database["source_mode"] = "Cached/Snapshot"
        database["source_name"] = "database history"
        database["collection_id"] = "database:collection-0"
        records = [provider, database, _record("PUBG", 1)]

        profile = _profile_from_records("creator-1", records, "Counter-Strike", ())

        self.assertEqual(profile.primary_category, "Counter-Strike")
        self.assertAlmostEqual(profile.primary_category_share, 1 / 2)

    def test_same_streamer_at_different_times_counts_multiple_observations(self):
        records = [
            _record("Counter-Strike", 0),
            _record("Counter-Strike", 1),
            _record("PUBG", 2),
        ]

        profile = _profile_from_records("creator-1", records, "Counter-Strike", ())

        self.assertAlmostEqual(profile.primary_category_share, 2 / 3)

    def test_empty_category_names_do_not_enter_frequency_denominator(self):
        records = [_record("Counter-Strike", 0), _record("", 1), _record("PUBG", 2)]

        profile = _profile_from_records("creator-1", records, "Counter-Strike", ())

        self.assertEqual(profile.primary_category, "Counter-Strike")
        self.assertAlmostEqual(profile.primary_category_share, 1 / 2)

    def test_display_category_history_is_ordered_and_deduplicated(self):
        records = [
            _record("Counter-Strike", 0),
            _record("PUBG", 1),
            _record("Counter-Strike", 2),
        ]

        profile = _profile_from_records("creator-1", records, "Counter-Strike", ())

        self.assertEqual(profile.category_history, ("Counter-Strike", "PUBG"))

    def test_pure_helper_returns_categories_in_chronological_order(self):
        records = [_record("PUBG", 2), _record("Counter-Strike", 0), _record("PUBG", 1)]

        aggregation = aggregate_creator_categories(records)

        self.assertEqual(
            aggregation.chronological_categories,
            ("Counter-Strike", "PUBG", "PUBG"),
        )
        self.assertEqual(aggregation.display_categories, ("Counter-Strike", "PUBG"))


if __name__ == "__main__":
    unittest.main()
