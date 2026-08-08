"""Small deterministic review analysis that works without an LLM."""

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


STOPWORDS = {"the", "and", "this", "that", "with", "for", "game", "very", "are", "was", "but", "you", "have", "from"}


# Ordered vocabulary keeps ties stable while making every topic rule inspectable.
TOPIC_VOCABULARY: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("combat", ("combat", "fight", "fighting", "weapon", "weapons", "attack", "attacks", "boss", "bosses")),
    ("gameplay", ("gameplay", "mechanic", "mechanics")),
    ("replayability", ("replay", "replayable", "replayability", "replaying")),
    ("story", ("story", "stories", "narrative", "plot", "writing", "character", "characters", "dialogue")),
    ("world", ("world", "exploration", "explore", "map", "maps", "environment", "level", "levels")),
    ("performance", ("bug", "bugs", "glitch", "glitches", "crash", "crashes", "lag", "stutter", "stuttering", "optimization", "performance", "fps", "loading")),
    ("bugs", ("bug", "bugs", "glitch", "glitches", "crash", "crashes")),
    ("balance", ("balance", "balanced", "unbalanced", "overpowered", "underpowered")),
    ("content", ("content", "endgame", "variety", "repetitive", "repetitious")),
    ("monetization", ("monetization", "microtransaction", "microtransactions", "paywall", "dlc", "dlcs")),
    ("progression", ("progression", "progress", "grind", "grindy", "grinding", "unlock", "unlocks", "loot", "leveling")),
    ("multiplayer", ("multiplayer", "coop", "cooperative", "online", "friends", "friend")),
    ("audio", ("music", "sound", "audio", "voice", "voices")),
    ("visuals", ("beautiful", "graphics", "visual", "visuals", "art", "artstyle")),
    ("controls", ("control", "controls", "controller", "keyboard", "mouse", "movement")),
    ("value", ("price", "cost", "value", "worth", "expensive", "cheap", "sale")),
)
TOPIC_KEYWORDS = TOPIC_VOCABULARY


@dataclass(frozen=True)
class ReviewTopic:
    """A topic found in a polarity bucket, counted once per matching review."""

    name: str
    count: int
    denominator: int
    percentage: float

    @property
    def label(self) -> str:
        return self.name

    @property
    def share(self) -> float:
        return self.percentage


@dataclass(frozen=True)
class ReviewPolarityBreakdown:
    """Recommendation counts and percentages over the complete review set."""

    positive_count: int = 0
    negative_count: int = 0
    unclassified_count: int = 0
    denominator: int = 0
    positive_percentage: float = 0.0
    negative_percentage: float = 0.0
    unclassified_percentage: float = 0.0

    @property
    def neutral_count(self) -> int:
        return self.unclassified_count

    @property
    def neutral_percentage(self) -> float:
        return self.unclassified_percentage


@dataclass(frozen=True)
class ReviewAnalysis:
    review_count: int
    positive_ratio: float
    positive_themes: tuple[str, ...]
    negative_themes: tuple[str, ...]
    excerpts: tuple[str, ...]
    praise_topics: tuple[ReviewTopic, ...] = ()
    complaint_topics: tuple[ReviewTopic, ...] = ()
    polarity_breakdown: ReviewPolarityBreakdown = field(default_factory=ReviewPolarityBreakdown)

    @property
    def positive_topics(self) -> tuple[ReviewTopic, ...]:
        return self.praise_topics

    @property
    def negative_topics(self) -> tuple[ReviewTopic, ...]:
        return self.complaint_topics

    @property
    def polarity(self) -> ReviewPolarityBreakdown:
        return self.polarity_breakdown


def _themes(texts: list[str]) -> tuple[str, ...]:
    counts = Counter()
    for text in texts:
        words = [word.casefold() for word in re.findall(r"[A-Za-z]{4,}", text)]
        counts.update(word for word in words if word not in STOPWORDS)
    return tuple(word for word, _ in counts.most_common(5))


def _topic_signals(texts: list[str]) -> tuple[ReviewTopic, ...]:
    denominator = len(texts)
    if not denominator:
        return ()
    counts = Counter()
    for text in texts:
        normalized = re.sub(r"\bco[\s-]+op\b", "coop", text.casefold())
        words = set(re.findall(r"[a-z0-9]+", normalized))
        for topic, keywords in TOPIC_VOCABULARY:
            if any(keyword in words for keyword in keywords):
                counts[topic] += 1
    order = {topic: index for index, (topic, _) in enumerate(TOPIC_VOCABULARY)}
    return tuple(
        ReviewTopic(topic, count, denominator, round(count / denominator, 4))
        for topic, count in sorted(counts.items(), key=lambda item: (-item[1], order[item[0]]))
        if count
    )


def _polarity_breakdown(rows: list[tuple[str, int | None]]) -> ReviewPolarityBreakdown:
    denominator = len(rows)
    if not denominator:
        return ReviewPolarityBreakdown()
    positive_count = sum(1 for _, recommended in rows if recommended is not None and bool(recommended))
    negative_count = sum(1 for _, recommended in rows if recommended is not None and not bool(recommended))
    unclassified_count = denominator - positive_count - negative_count
    return ReviewPolarityBreakdown(
        positive_count=positive_count,
        negative_count=negative_count,
        unclassified_count=unclassified_count,
        denominator=denominator,
        positive_percentage=round(positive_count / denominator, 4),
        negative_percentage=round(negative_count / denominator, 4),
        unclassified_percentage=round(unclassified_count / denominator, 4),
    )


def analyze_reviews(database_path: Path, app_id: int, limit: int = 5000) -> ReviewAnalysis:
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT review_text, recommended FROM reviews WHERE steam_app_id = ? ORDER BY created_at_unix DESC LIMIT ?", (app_id, max(1, min(limit, 10000)))).fetchall()
    finally:
        connection.close()
    if not rows:
        return ReviewAnalysis(0, 0.0, (), (), ())
    positive = [text for text, recommended in rows if recommended]
    negative = [text for text, recommended in rows if recommended is not None and not recommended]
    excerpts = tuple(text[:280].replace("\n", " ") for text, _ in rows[:5])
    return ReviewAnalysis(
        len(rows),
        round(len(positive) / len(rows), 4),
        _themes(positive),
        _themes(negative),
        excerpts,
        _topic_signals(positive),
        _topic_signals(negative),
        _polarity_breakdown(rows),
    )
