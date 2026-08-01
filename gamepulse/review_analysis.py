"""Small deterministic review analysis that works without an LLM."""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


STOPWORDS = {"the", "and", "this", "that", "with", "for", "game", "very", "are", "was", "but", "you", "have", "from"}


@dataclass(frozen=True)
class ReviewAnalysis:
    review_count: int
    positive_ratio: float
    positive_themes: tuple[str, ...]
    negative_themes: tuple[str, ...]
    excerpts: tuple[str, ...]


def _themes(texts: list[str]) -> tuple[str, ...]:
    counts = Counter()
    for text in texts:
        words = [word.casefold() for word in re.findall(r"[A-Za-z]{4,}", text)]
        counts.update(word for word in words if word not in STOPWORDS)
    return tuple(word for word, _ in counts.most_common(5))


def analyze_reviews(database_path: Path, app_id: int, limit: int = 5000) -> ReviewAnalysis:
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT review_text, recommended FROM reviews WHERE steam_app_id = ? ORDER BY created_at_unix DESC LIMIT ?", (app_id, max(1, min(limit, 10000)))).fetchall()
    finally:
        connection.close()
    if not rows:
        return ReviewAnalysis(0, 0.0, (), (), ())
    positive = [text for text, recommended in rows if recommended]
    negative = [text for text, recommended in rows if not recommended]
    excerpts = tuple(text[:280].replace("\n", " ") for text, _ in rows[:5])
    return ReviewAnalysis(len(rows), round(len(positive) / len(rows), 4), _themes(positive), _themes(negative), excerpts)

