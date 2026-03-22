"""Tests for article deduplication."""

import pytest

from src.dedup import ArticleDeduplicator
from src.sources.base import RawArticle


def _make_article(
    title: str = "テスト記事",
    url: str = "https://example.com/1",
    date: str = "2026-03-15",
    source: str = "TestSource",
    genre: str = "AI",
) -> RawArticle:
    return RawArticle(
        title=title,
        url=url,
        published_date=date,
        source_name=source,
        genre_query=genre,
    )


class TestArticleDeduplicator:
    def setup_method(self):
        self.dedup = ArticleDeduplicator()

    def test_empty_input(self):
        assert self.dedup.process([]) == []

    def test_no_duplicates(self):
        articles = [
            _make_article(title="記事A", url="https://a.com/1"),
            _make_article(title="記事B", url="https://b.com/2"),
        ]
        result = self.dedup.process(articles)
        assert len(result) == 2

    def test_url_dedup_exact(self):
        articles = [
            _make_article(title="記事A", url="https://example.com/article/1"),
            _make_article(title="記事B", url="https://example.com/article/1"),
        ]
        result = self.dedup.process(articles)
        assert len(result) == 1

    def test_url_dedup_query_params(self):
        """Same URL with different query params should be deduplicated."""
        articles = [
            _make_article(title="記事A", url="https://example.com/article/1"),
            _make_article(title="記事B", url="https://example.com/article/1?ref=rss"),
        ]
        result = self.dedup.process(articles)
        assert len(result) == 1

    def test_title_similarity_dedup(self):
        """Very similar titles should be deduplicated."""
        articles = [
            _make_article(
                title="AIが変える未来の働き方 最新トレンドまとめ",
                url="https://a.com/1",
            ),
            _make_article(
                title="AIが変える未来の働き方 最新トレンド",
                url="https://b.com/2",
            ),
        ]
        result = self.dedup.process(articles)
        assert len(result) == 1

    def test_different_titles_kept(self):
        """Different titles should be kept."""
        articles = [
            _make_article(
                title="AIが変える未来の働き方",
                url="https://a.com/1",
            ),
            _make_article(
                title="量子コンピュータの最新動向",
                url="https://b.com/2",
            ),
        ]
        result = self.dedup.process(articles)
        assert len(result) == 2

    def test_max_items_limit(self):
        articles = [
            _make_article(title=f"記事{i}", url=f"https://example.com/{i}")
            for i in range(20)
        ]
        result = self.dedup.process(articles, max_items=5)
        assert len(result) == 5

    def test_freshness_ranking(self):
        """Newer articles should be ranked higher."""
        articles = [
            _make_article(title="古い記事", url="https://a.com/1", date="2026-03-01"),
            _make_article(title="新しい記事", url="https://b.com/2", date="2026-03-15"),
        ]
        result = self.dedup.process(articles)
        assert result[0].title == "新しい記事"

    def test_genre_diversity(self):
        """Articles from different genres should be mixed."""
        articles = [
            _make_article(title="AI記事1", url="https://a.com/1", genre="AI", date="2026-03-15"),
            _make_article(title="AI記事2", url="https://a.com/2", genre="AI", date="2026-03-15"),
            _make_article(title="AI記事3", url="https://a.com/3", genre="AI", date="2026-03-15"),
            _make_article(title="DX記事1", url="https://b.com/1", genre="DX", date="2026-03-15"),
        ]
        result = self.dedup.process(articles, max_items=4)
        # DX article should be boosted relative to 3rd AI article
        genres = [a.genre_query for a in result]
        assert "DX" in genres


class TestJaccardSimilarity:
    def test_identical(self):
        dedup = ArticleDeduplicator()
        tokens = dedup._tokenize("テスト文字列")
        assert dedup._jaccard_similarity(tokens, tokens) == 1.0

    def test_completely_different(self):
        dedup = ArticleDeduplicator()
        a = dedup._tokenize("あいうえお")
        b = dedup._tokenize("かきくけこ")
        assert dedup._jaccard_similarity(a, b) == 0.0

    def test_partial_overlap(self):
        dedup = ArticleDeduplicator()
        a = dedup._tokenize("AIの最新動向")
        b = dedup._tokenize("AIの今後の展望")
        sim = dedup._jaccard_similarity(a, b)
        assert 0.0 < sim < 1.0

    def test_empty_sets(self):
        dedup = ArticleDeduplicator()
        assert dedup._jaccard_similarity(set(), set()) == 0.0


class TestNormalizeUrl:
    def test_removes_query_params(self):
        dedup = ArticleDeduplicator()
        result = dedup._normalize_url("https://example.com/article?ref=rss&utm=test")
        assert result == "https://example.com/article"

    def test_removes_fragment(self):
        dedup = ArticleDeduplicator()
        result = dedup._normalize_url("https://example.com/article#section1")
        assert result == "https://example.com/article"

    def test_preserves_path(self):
        dedup = ArticleDeduplicator()
        result = dedup._normalize_url("https://example.com/2026/03/article-title")
        assert result == "https://example.com/2026/03/article-title"

    def test_youtube_preserves_video_id(self):
        dedup = ArticleDeduplicator()
        result = dedup._normalize_url("https://www.youtube.com/watch?v=abc123")
        assert result == "https://www.youtube.com/watch?v=abc123"

    def test_youtube_strips_extra_params(self):
        dedup = ArticleDeduplicator()
        result = dedup._normalize_url(
            "https://www.youtube.com/watch?v=abc123&list=PLxxx&t=30"
        )
        assert result == "https://www.youtube.com/watch?v=abc123"

    def test_youtube_different_videos_not_deduped(self):
        dedup = ArticleDeduplicator()
        a = dedup._normalize_url("https://www.youtube.com/watch?v=abc123")
        b = dedup._normalize_url("https://www.youtube.com/watch?v=xyz789")
        assert a != b
