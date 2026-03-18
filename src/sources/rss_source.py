"""Direct RSS feed source for tech news sites."""

import logging

import feedparser

from .base import NewsSource, RawArticle, parse_feed_date

logger = logging.getLogger(__name__)


class RssSource(NewsSource):
    """Fetch articles from direct RSS feeds (ITmedia, Publickey, etc.)."""

    source_id = "rss"

    def __init__(self, feeds: list[dict], timeout: int = 15):
        """
        Args:
            feeds: List of feed configs, e.g.
                [{"url": "https://...", "name": "ITmedia AI+"}]
            timeout: Request timeout in seconds
        """
        self.feeds = feeds
        self.timeout = timeout

    def fetch(self, genres: list[str], max_per_genre: int = 5) -> list[RawArticle]:
        articles: list[RawArticle] = []
        genre_keywords = [g.lower() for g in genres]

        for feed_config in self.feeds:
            try:
                feed_articles = self._fetch_feed(
                    feed_config, genre_keywords, max_per_genre
                )
                articles.extend(feed_articles)
                logger.info(
                    "RSS: %d articles from '%s'",
                    len(feed_articles),
                    feed_config.get("name", feed_config["url"]),
                )
            except Exception:
                logger.exception(
                    "RSS: failed to fetch '%s'",
                    feed_config.get("name", feed_config["url"]),
                )

        return articles

    def is_available(self) -> bool:
        return len(self.feeds) > 0

    def _fetch_feed(
        self,
        feed_config: dict,
        genre_keywords: list[str],
        max_items: int,
    ) -> list[RawArticle]:
        url = feed_config["url"]
        feed_name = feed_config.get("name", url)

        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            raise RuntimeError(
                f"Failed to parse RSS feed '{feed_name}': {feed.bozo_exception}"
            )

        results: list[RawArticle] = []
        for entry in feed.entries:
            if len(results) >= max_items:
                break

            title = entry.get("title", "")
            summary = entry.get("summary", "")
            text_to_match = (title + " " + summary).lower()

            # Match against genre keywords
            matched_genre = self._match_genre(text_to_match, genre_keywords)
            if not matched_genre:
                continue

            published_date = parse_feed_date(entry)
            article_url = entry.get("link", "")
            content_type = (
                "youtube" if "youtube.com" in article_url else "article"
            )

            results.append(
                RawArticle(
                    title=title,
                    url=article_url,
                    published_date=published_date,
                    source_name=feed_name,
                    content_snippet=summary,
                    content_type=content_type,
                    genre_query=matched_genre,
                )
            )

        return results

    @staticmethod
    def _match_genre(text: str, genre_keywords: list[str]) -> str:
        """Return the first matching genre keyword, or empty string."""
        for keyword in genre_keywords:
            if keyword in text:
                return keyword
        return ""

