"""Google News RSS source for Japanese news."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import quote

import feedparser

from .base import NewsSource, RawArticle, parse_feed_date

if TYPE_CHECKING:
    from ..query_builder import SearchQuery

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS_URL = (
    "https://news.google.com/rss/search"
    "?q={query}+when:{days}d&hl=ja&gl=JP&ceid=JP:ja"
)


class GoogleNewsSource(NewsSource):
    """Fetch Japanese news from Google News RSS."""

    source_id = "google_news"

    def __init__(self, days: int = 7, timeout: int = 15):
        self.days = days
        self.timeout = timeout

    def fetch(self, genres: list[str], max_per_genre: int = 5) -> list[RawArticle]:
        articles: list[RawArticle] = []

        for genre in genres:
            try:
                genre_articles = self._fetch_genre(genre, max_per_genre)
                articles.extend(genre_articles)
                logger.info(
                    "Google News: %d articles for '%s'",
                    len(genre_articles),
                    genre,
                )
            except Exception:
                logger.exception("Google News: failed to fetch genre '%s'", genre)

        return articles

    def fetch_by_queries(
        self, queries: list[SearchQuery], max_per_query: int = 5
    ) -> list[RawArticle]:
        """Fetch articles using pre-built SearchQuery objects.

        Each query already contains the composite search string and source type.
        """
        articles: list[RawArticle] = []

        for sq in queries:
            try:
                query_str = sq.query
                if sq.source_type == "youtube":
                    query_str = f"{sq.query} site:youtube.com"

                query_articles = self._fetch_genre(query_str, max_per_query)
                for a in query_articles:
                    a.genre_query = sq.genre_label
                    # Google News RSS returns redirect URLs (news.google.com/rss/articles/...)
                    # that don't contain youtube.com, so override based on query source_type.
                    if sq.source_type == "youtube":
                        a.content_type = "youtube"
                articles.extend(query_articles)
                logger.info(
                    "Google News [%s]: %d articles for '%s'",
                    sq.source_type,
                    len(query_articles),
                    sq.query,
                )
            except Exception:
                logger.exception(
                    "Google News: failed query '%s'", sq.query
                )

        return articles

    def is_available(self) -> bool:
        """Google News RSS is always available (no API key needed)."""
        return True

    def _fetch_genre(self, genre: str, max_items: int) -> list[RawArticle]:
        url = GOOGLE_NEWS_RSS_URL.format(
            query=quote(genre),
            days=self.days,
        )

        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            raise RuntimeError(
                f"Failed to parse Google News RSS: {feed.bozo_exception}"
            )

        results: list[RawArticle] = []
        for entry in feed.entries[:max_items]:
            published_date = parse_feed_date(entry)
            article_url = entry.get("link", "")
            content_type = (
                "youtube" if "youtube.com" in article_url else "article"
            )

            # Google News titles often have " - Source" suffix
            title = entry.get("title", "")
            source_name = "Google News"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source_name = parts[1]

            results.append(
                RawArticle(
                    title=title,
                    url=article_url,
                    published_date=published_date,
                    source_name=source_name,
                    content_snippet=entry.get("summary", ""),
                    content_type=content_type,
                    genre_query=genre,
                )
            )

        return results

