"""Tests for content filter."""

from src.content_filter import ContentFilter
from src.sources.base import RawArticle


def _make_article(
    title: str = "テスト記事",
    url: str = "https://example.com/article",
    snippet: str = "",
    content_type: str = "article",
    genre_query: str = "AI",
) -> RawArticle:
    return RawArticle(
        title=title,
        url=url,
        published_date="2026-03-15",
        source_name="TestSource",
        content_snippet=snippet,
        content_type=content_type,
        genre_query=genre_query,
    )


class TestNoisePatternFilter:
    def test_excludes_dance_video(self):
        f = ContentFilter()
        articles = [_make_article(title="【踊ってみた】AI風ダンス")]
        result = f.apply(articles)
        assert len(result) == 0

    def test_excludes_singing_video(self):
        f = ContentFilter()
        articles = [_make_article(title="歌ってみた AI生成ボイス")]
        result = f.apply(articles)
        assert len(result) == 0

    def test_excludes_lovelive(self):
        f = ContentFilter()
        articles = [_make_article(title="ラブライブ 新AI機能")]
        result = f.apply(articles)
        assert len(result) == 0

    def test_passes_tech_article(self):
        f = ContentFilter()
        articles = [_make_article(
            title="OpenAIが新モデル発表 企業向け機能を強化",
            snippet="GPT-5の開発が進む中、企業向けAPI機能を拡充",
        )]
        result = f.apply(articles)
        assert len(result) == 1

    def test_noise_in_snippet_also_excluded(self):
        f = ContentFilter()
        articles = [_make_article(
            title="普通のタイトル",
            snippet="ラブライブの最新情報",
        )]
        result = f.apply(articles)
        assert len(result) == 0


class TestDomainBlacklist:
    def test_excludes_pixiv(self):
        f = ContentFilter()
        articles = [_make_article(url="https://www.pixiv.net/artworks/12345")]
        result = f.apply(articles)
        assert len(result) == 0

    def test_excludes_nicovideo(self):
        f = ContentFilter()
        articles = [_make_article(url="https://www.nicovideo.jp/watch/sm12345")]
        result = f.apply(articles)
        assert len(result) == 0

    def test_youtube_not_blacklisted(self):
        f = ContentFilter()
        articles = [_make_article(
            url="https://www.youtube.com/watch?v=test",
            content_type="youtube",
            title="AI開発の最新動向",
            snippet="機械学習の新手法について解説",
        )]
        result = f.apply(articles)
        assert len(result) == 1

    def test_passes_normal_domain(self):
        f = ContentFilter()
        articles = [_make_article(
            url="https://www.itmedia.co.jp/ai/article.html",
            title="AI最新ニュース",
            snippet="機械学習の企業導入が進む",
        )]
        result = f.apply(articles)
        assert len(result) == 1


class TestTechCooccurrence:
    def test_ambiguous_keyword_without_tech_words_excluded(self):
        f = ContentFilter()
        articles = [_make_article(
            title="映画「AI」の感想レビュー",
            snippet="スピルバーグ監督作品の名作",
            genre_query="AI",
        )]
        result = f.apply(articles)
        assert len(result) == 0

    def test_ambiguous_keyword_with_tech_words_passes(self):
        f = ContentFilter()
        articles = [_make_article(
            title="AI導入で企業の開発効率が向上",
            snippet="機械学習モデルの活用事例",
            genre_query="AI",
        )]
        result = f.apply(articles)
        assert len(result) == 1

    def test_specific_keyword_skips_cooccurrence_check(self):
        """Non-ambiguous keywords (e.g. Claude Code) skip co-occurrence check."""
        f = ContentFilter()
        articles = [_make_article(
            title="Claude Code の使い方",
            snippet="普通の説明文",
            genre_query="Claude Code",
        )]
        result = f.apply(articles)
        assert len(result) == 1

    def test_cooccurrence_case_insensitive(self):
        f = ContentFilter()
        articles = [_make_article(
            title="AIとGPTの未来",
            snippet="最新のテクノロジー",
            genre_query="AI",
        )]
        result = f.apply(articles)
        assert len(result) == 1


class TestFilterChain:
    def test_multiple_articles_mixed(self):
        f = ContentFilter()
        articles = [
            _make_article(
                title="OpenAI新モデル発表",
                snippet="企業向けAPI機能強化",
                genre_query="AI",
            ),
            _make_article(
                title="踊ってみた AIダンス",
                genre_query="AI",
            ),
            _make_article(
                title="AI映画レビュー",
                snippet="スピルバーグ作品",
                genre_query="AI",
            ),
            _make_article(
                title="Claude Code入門",
                snippet="プログラミング解説",
                genre_query="Claude Code",
            ),
        ]
        result = f.apply(articles)
        # Article 1: passes (tech co-occurrence)
        # Article 2: excluded (noise pattern)
        # Article 3: excluded (no tech co-occurrence for ambiguous "AI")
        # Article 4: passes (non-ambiguous keyword)
        assert len(result) == 2
        assert result[0].title == "OpenAI新モデル発表"
        assert result[1].title == "Claude Code入門"
