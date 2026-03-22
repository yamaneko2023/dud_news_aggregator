"""Tests for hatena_collector module."""

from collections import Counter
from unittest.mock import patch

import pytest

from src.keyword_optimizer.hatena_collector import (
    collect_trending_keywords,
    extract_keywords_from_titles,
    fetch_hatena_entries,
)


class TestExtractKeywordsFromTitles:
    def test_camel_case(self):
        titles = ["ChatGPTを使った開発", "FastAPIでAPI構築"]
        counter = extract_keywords_from_titles(titles)
        assert "ChatGPT" in counter
        assert "FastAPI" in counter

    def test_uppercase_tech_terms(self):
        titles = ["LLMの最新動向", "AWS Lambda入門", "GPT-4oリリース"]
        counter = extract_keywords_from_titles(titles)
        assert "LLM" in counter
        assert "AWS" in counter
        assert "GPT-4o" in counter

    def test_katakana_extraction(self):
        titles = ["クラウドネイティブの時代", "コンテナオーケストレーション"]
        counter = extract_keywords_from_titles(titles)
        assert "クラウドネイティブ" in counter
        assert "コンテナオーケストレーション" in counter

    def test_stop_words_excluded(self):
        titles = ["The new API for web app", "サービスのシステム開発"]
        counter = extract_keywords_from_titles(titles)
        assert "The" not in counter
        assert "サービス" not in counter
        assert "システム" not in counter

    def test_stop_words_site_names_excluded(self):
        titles = [
            "DevelopersIOで話題の記事",
            "Qiitaのトレンド",
            "GitHub Actionsを使う",
            "Publickeyの最新記事",
            "GIGAZINEまとめ",
        ]
        counter = extract_keywords_from_titles(titles)
        assert "DevelopersIO" not in counter
        assert "Qiita" not in counter
        assert "GitHub" not in counter
        assert "Publickey" not in counter
        assert "GIGAZINE" not in counter

    def test_stop_words_generic_english_excluded(self):
        titles = [
            "Code reviewの方法",
            "Google Cloudの新機能",
            "Pythonで開発",
            "Linux入門",
        ]
        counter = extract_keywords_from_titles(titles)
        assert "Code" not in counter
        assert "Google" not in counter
        assert "Python" not in counter
        assert "Linux" not in counter

    def test_stop_words_generic_japanese_excluded(self):
        titles = ["リリース情報", "アップデートまとめ", "ニュースレビュー"]
        counter = extract_keywords_from_titles(titles)
        assert "リリース" not in counter
        assert "アップデート" not in counter
        assert "ニュース" not in counter
        assert "レビュー" not in counter

    def test_short_words_excluded(self):
        titles = ["I am a developer"]
        counter = extract_keywords_from_titles(titles)
        assert "I" not in counter

    def test_frequency_counting(self):
        titles = ["ChatGPT活用法", "ChatGPTの使い方", "LLM入門"]
        counter = extract_keywords_from_titles(titles)
        assert counter["ChatGPT"] == 2
        assert counter["LLM"] == 1

    def test_empty_titles(self):
        counter = extract_keywords_from_titles([])
        assert len(counter) == 0

    def test_katakana_min_length(self):
        titles = ["AIの発展"]
        counter = extract_keywords_from_titles(titles)
        # "AI" should match as uppercase, but katakana needs 3+ chars
        assert "AI" in counter


class TestFetchHatenaEntries:
    @patch("src.keyword_optimizer.hatena_collector.feedparser.parse")
    def test_normal_entries(self, mock_parse):
        mock_parse.return_value = type("Feed", (), {
            "bozo": False,
            "entries": [
                {"title": "テスト記事1", "link": "https://example.com/1"},
                {"title": "テスト記事2", "link": "https://example.com/2"},
            ],
        })()
        entries = fetch_hatena_entries("http://test.rss")
        assert len(entries) == 2
        assert entries[0]["title"] == "テスト記事1"

    @patch("src.keyword_optimizer.hatena_collector.feedparser.parse")
    def test_empty_feed(self, mock_parse):
        mock_parse.return_value = type("Feed", (), {
            "bozo": True,
            "bozo_exception": Exception("parse error"),
            "entries": [],
        })()
        entries = fetch_hatena_entries("http://test.rss")
        assert entries == []

    @patch("src.keyword_optimizer.hatena_collector.feedparser.parse")
    def test_skip_empty_titles(self, mock_parse):
        mock_parse.return_value = type("Feed", (), {
            "bozo": False,
            "entries": [
                {"title": "", "link": "https://example.com/1"},
                {"title": "有効な記事", "link": "https://example.com/2"},
            ],
        })()
        entries = fetch_hatena_entries("http://test.rss")
        assert len(entries) == 1


class TestCollectTrendingKeywords:
    @patch("src.keyword_optimizer.hatena_collector.fetch_hatena_entries")
    def test_collect_with_min_frequency(self, mock_fetch):
        mock_fetch.return_value = [
            {"title": "ChatGPTで開発", "link": ""},
            {"title": "ChatGPT活用", "link": ""},
            {"title": "LLM入門", "link": ""},
        ]
        results = collect_trending_keywords(min_frequency=2)
        keywords = [r["keyword"] for r in results]
        assert "ChatGPT" in keywords
        assert "LLM" not in keywords  # frequency=1, below threshold

    @patch("src.keyword_optimizer.hatena_collector.fetch_hatena_entries")
    def test_result_format(self, mock_fetch):
        mock_fetch.return_value = [
            {"title": "ChatGPTの使い方", "link": ""},
            {"title": "ChatGPT活用術", "link": ""},
        ]
        results = collect_trending_keywords(min_frequency=1)
        assert len(results) > 0
        result = results[0]
        assert "keyword" in result
        assert "frequency" in result
        assert result["source"] == "hatena"

    @patch("src.keyword_optimizer.hatena_collector.fetch_hatena_entries")
    def test_empty_entries(self, mock_fetch):
        mock_fetch.return_value = []
        results = collect_trending_keywords()
        assert results == []

    @patch("src.keyword_optimizer.hatena_collector.fetch_hatena_entries")
    def test_sorted_by_frequency(self, mock_fetch):
        mock_fetch.return_value = [
            {"title": "LLM入門", "link": ""},
            {"title": "ChatGPTで開発", "link": ""},
            {"title": "ChatGPT活用", "link": ""},
            {"title": "ChatGPTの比較", "link": ""},
        ]
        results = collect_trending_keywords(min_frequency=1)
        freqs = [r["frequency"] for r in results]
        assert freqs == sorted(freqs, reverse=True)
