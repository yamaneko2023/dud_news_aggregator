"""News source base classes and data models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawArticle:
    """A single raw article fetched from a news source."""

    title: str
    url: str
    published_date: str  # YYYY-MM-DD
    source_name: str  # "Google News", "ITmedia" etc.
    content_snippet: str = ""
    content_type: str = "article"  # "article" | "youtube"
    score: float = 0.0
    genre_query: str = ""


def parse_feed_date(entry) -> str:
    """Parse published/updated date from feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6]).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                pass
    return datetime.now().strftime("%Y-%m-%d")


class NewsSource(ABC):
    """Abstract base class for news sources."""

    source_id: str = ""

    @abstractmethod
    def fetch(self, genres: list[str], max_per_genre: int = 5) -> list[RawArticle]:
        """Fetch articles for the given genres.

        Args:
            genres: List of genre keywords (e.g. ["AI", "Claude Code"])
            max_per_genre: Maximum articles to fetch per genre

        Returns:
            List of RawArticle objects
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this source is currently available."""
        ...
