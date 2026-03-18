"""Tests for WEB:YouTube mix ratio control."""

import os
import sys

# Project root setup for importing scripts/fetch_news
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scripts.fetch_news import apply_mix_ratio
from src.sources.base import RawArticle


def _make_web(n: int) -> list[RawArticle]:
    return [
        RawArticle(
            title=f"Web Article {i}",
            url=f"https://example.com/{i}",
            published_date="2026-03-15",
            source_name="Web",
            content_type="article",
        )
        for i in range(n)
    ]


def _make_yt(n: int) -> list[RawArticle]:
    return [
        RawArticle(
            title=f"YouTube Video {i}",
            url=f"https://youtube.com/{i}",
            published_date="2026-03-15",
            source_name="YouTube",
            content_type="youtube",
        )
        for i in range(n)
    ]


class TestMixRatio:
    def test_standard_7_3_ratio(self):
        """Standard case: enough of both types."""
        articles = _make_web(12) + _make_yt(5)
        result = apply_mix_ratio(articles, web_ratio=7, yt_ratio=3, max_items=10)
        web = [a for a in result if a.content_type != "youtube"]
        yt = [a for a in result if a.content_type == "youtube"]
        assert len(web) == 7
        assert len(yt) == 3
        assert len(result) == 10

    def test_insufficient_youtube(self):
        """Not enough YouTube: fill with more web."""
        articles = _make_web(12) + _make_yt(1)
        result = apply_mix_ratio(articles, web_ratio=7, yt_ratio=3, max_items=10)
        web = [a for a in result if a.content_type != "youtube"]
        yt = [a for a in result if a.content_type == "youtube"]
        assert len(yt) == 1
        assert len(web) == 9
        assert len(result) == 10

    def test_insufficient_web(self):
        """Not enough web: fill with more YouTube."""
        articles = _make_web(3) + _make_yt(10)
        result = apply_mix_ratio(articles, web_ratio=7, yt_ratio=3, max_items=10)
        web = [a for a in result if a.content_type != "youtube"]
        yt = [a for a in result if a.content_type == "youtube"]
        assert len(web) == 3
        assert len(yt) == 7
        assert len(result) == 10

    def test_no_youtube(self):
        """All web when no YouTube available."""
        articles = _make_web(15)
        result = apply_mix_ratio(articles, web_ratio=7, yt_ratio=3, max_items=10)
        assert len(result) == 10
        assert all(a.content_type == "article" for a in result)

    def test_no_web(self):
        """All YouTube when no web available."""
        articles = _make_yt(15)
        result = apply_mix_ratio(articles, web_ratio=7, yt_ratio=3, max_items=10)
        assert len(result) == 10
        assert all(a.content_type == "youtube" for a in result)

    def test_fewer_than_max_items(self):
        """Total articles less than max_items."""
        articles = _make_web(3) + _make_yt(2)
        result = apply_mix_ratio(articles, web_ratio=7, yt_ratio=3, max_items=10)
        assert len(result) == 5

    def test_5_5_ratio(self):
        """Equal 5:5 ratio."""
        articles = _make_web(10) + _make_yt(10)
        result = apply_mix_ratio(articles, web_ratio=5, yt_ratio=5, max_items=10)
        web = [a for a in result if a.content_type != "youtube"]
        yt = [a for a in result if a.content_type == "youtube"]
        assert len(web) == 5
        assert len(yt) == 5

    def test_empty_input(self):
        result = apply_mix_ratio([], web_ratio=7, yt_ratio=3, max_items=10)
        assert result == []
