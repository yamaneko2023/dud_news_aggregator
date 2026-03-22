"""Tests for Google News RSS source."""

import os
from unittest.mock import patch

import feedparser
import pytest

from src.query_builder import SearchQuery
from src.sources.google_news import GoogleNewsSource

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Load fixture BEFORE any mocking to get real feedparser results
_GOOGLE_NEWS_FIXTURE = feedparser.parse(
    open(os.path.join(FIXTURES_DIR, "google_news_sample.xml"), encoding="utf-8").read()
)


class TestGoogleNewsSource:
    def test_is_available(self):
        source = GoogleNewsSource()
        assert source.is_available() is True

    def test_source_id(self):
        source = GoogleNewsSource()
        assert source.source_id == "google_news"

    @patch("src.sources.google_news.feedparser.parse")
    def test_fetch_parses_articles(self, mock_parse):
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        source = GoogleNewsSource()
        articles = source.fetch(["AI"], max_per_genre=5)

        assert len(articles) == 5
        assert articles[0].title == "AIが変える未来の働き方 最新トレンドまとめ"
        assert articles[0].source_name == "ITmedia"
        assert articles[0].genre_query == "AI"

    @patch("src.sources.google_news.feedparser.parse")
    def test_youtube_detection(self, mock_parse):
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        source = GoogleNewsSource()
        articles = source.fetch(["AI"], max_per_genre=5)

        youtube_articles = [a for a in articles if a.content_type == "youtube"]
        assert len(youtube_articles) == 1
        assert "youtube.com" in youtube_articles[0].url

    @patch("src.sources.google_news.feedparser.parse")
    def test_source_name_extraction(self, mock_parse):
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        source = GoogleNewsSource()
        articles = source.fetch(["AI"], max_per_genre=5)

        source_names = [a.source_name for a in articles]
        assert "ITmedia" in source_names
        assert "Publickey" in source_names

    @patch("src.sources.google_news.feedparser.parse")
    def test_date_parsing(self, mock_parse):
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        source = GoogleNewsSource()
        articles = source.fetch(["AI"], max_per_genre=5)

        assert articles[0].published_date == "2026-03-15"
        assert articles[1].published_date == "2026-03-14"

    @patch("src.sources.google_news.feedparser.parse")
    def test_max_per_genre_limit(self, mock_parse):
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        source = GoogleNewsSource()
        articles = source.fetch(["AI"], max_per_genre=2)

        assert len(articles) == 2

    @patch("src.sources.google_news.feedparser.parse")
    def test_multiple_genres(self, mock_parse):
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        source = GoogleNewsSource()
        articles = source.fetch(["AI", "DX"], max_per_genre=3)

        # Each genre call returns up to 3, called twice
        assert mock_parse.call_count == 2

    @patch("src.sources.google_news.feedparser.parse")
    def test_empty_feed(self, mock_parse):
        empty_feed = feedparser.FeedParserDict()
        empty_feed["entries"] = []
        empty_feed["bozo"] = False
        mock_parse.return_value = empty_feed

        source = GoogleNewsSource()
        articles = source.fetch(["AI"])
        assert articles == []

    @patch("src.sources.google_news.feedparser.parse")
    def test_fetch_by_queries(self, mock_parse):
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        queries = [
            SearchQuery(query="テクノロジー AI", genre_label="AI", source_type="web"),
            SearchQuery(query="テクノロジー AI", genre_label="AI", source_type="youtube"),
        ]

        source = GoogleNewsSource()
        articles = source.fetch_by_queries(queries, max_per_query=3)

        # 2 queries * up to 3 each
        assert mock_parse.call_count == 2
        assert len(articles) <= 6
        # genre_label should be overridden
        assert all(a.genre_query == "AI" for a in articles)

        # Verify YouTube query has site:youtube.com appended
        calls = mock_parse.call_args_list
        web_url = calls[0][0][0]
        yt_url = calls[1][0][0]
        assert "site%3Ayoutube.com" not in web_url
        assert "site%3Ayoutube.com" in yt_url

    @patch("src.sources.google_news.feedparser.parse")
    def test_fetch_by_queries_youtube_appends_site_filter(self, mock_parse):
        """YouTube queries must include site:youtube.com in the RSS URL."""
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        queries = [
            SearchQuery(
                query="テクノロジー AI",
                genre_label="AI",
                source_type="youtube",
            ),
        ]

        source = GoogleNewsSource()
        source.fetch_by_queries(queries, max_per_query=3)

        # The URL passed to feedparser should contain the encoded site:youtube.com
        called_url = mock_parse.call_args[0][0]
        assert "site%3Ayoutube.com" in called_url

    @patch("src.sources.google_news.feedparser.parse")
    def test_fetch_by_queries_web_no_site_filter(self, mock_parse):
        """Web queries must NOT include site:youtube.com."""
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        queries = [
            SearchQuery(
                query="テクノロジー AI",
                genre_label="AI",
                source_type="web",
            ),
        ]

        source = GoogleNewsSource()
        source.fetch_by_queries(queries, max_per_query=3)

        called_url = mock_parse.call_args[0][0]
        assert "site%3Ayoutube.com" not in called_url

    @patch("src.sources.google_news.feedparser.parse")
    def test_fetch_by_queries_sets_genre_label(self, mock_parse):
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        queries = [
            SearchQuery(
                query="テクノロジー Claude Code",
                genre_label="Claude Code",
                source_type="web",
            ),
        ]

        source = GoogleNewsSource()
        articles = source.fetch_by_queries(queries, max_per_query=2)

        assert len(articles) == 2
        assert all(a.genre_query == "Claude Code" for a in articles)

    @patch("src.sources.google_news.feedparser.parse")
    def test_fetch_by_queries_youtube_overrides_content_type(self, mock_parse):
        """YouTube queries must set content_type='youtube' regardless of URL."""
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        queries = [
            SearchQuery(query="AI", genre_label="AI", source_type="youtube"),
        ]

        source = GoogleNewsSource()
        articles = source.fetch_by_queries(queries, max_per_query=5)

        # ALL articles from a youtube query should be typed as youtube,
        # even if their URL is a Google News redirect (no youtube.com in URL).
        assert all(a.content_type == "youtube" for a in articles)

    @patch("src.sources.google_news.feedparser.parse")
    def test_fetch_by_queries_web_preserves_original_type(self, mock_parse):
        """Web queries should not override content_type."""
        mock_parse.return_value = _GOOGLE_NEWS_FIXTURE

        queries = [
            SearchQuery(query="AI", genre_label="AI", source_type="web"),
        ]

        source = GoogleNewsSource()
        articles = source.fetch_by_queries(queries, max_per_query=5)

        # Web queries keep the URL-based detection (mostly "article")
        article_types = [a.content_type for a in articles]
        assert "article" in article_types
