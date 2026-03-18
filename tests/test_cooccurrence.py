"""Tests for cooccurrence module."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.keyword_optimizer.cooccurrence import (
    analyze_cooccurrence,
    compute_cooccurrence,
    extract_nouns,
    load_past_titles,
)


class TestLoadPastTitles:
    def test_wrapper_format(self, tmp_path):
        data = {
            "fetched_at": "2026-03-17 09:00:00",
            "count": 2,
            "items": [
                {"id": 1, "title": "AIの最新動向"},
                {"id": 2, "title": "LLM活用事例"},
            ],
        }
        path = str(tmp_path / "news.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        titles = load_past_titles(path)
        assert titles == ["AIの最新動向", "LLM活用事例"]

    def test_list_format(self, tmp_path):
        data = [
            {"title": "記事1"},
            {"title": "記事2"},
        ]
        path = str(tmp_path / "news.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        titles = load_past_titles(path)
        assert titles == ["記事1", "記事2"]

    def test_missing_file(self):
        titles = load_past_titles("/nonexistent/path.json")
        assert titles == []

    def test_invalid_json(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("not json")
        titles = load_past_titles(path)
        assert titles == []

    def test_items_without_title(self, tmp_path):
        data = {"items": [{"id": 1}, {"id": 2, "title": "有効"}]}
        path = str(tmp_path / "news.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        titles = load_past_titles(path)
        assert titles == ["有効"]


# Only run janome-dependent tests if janome is available
try:
    from janome.tokenizer import Tokenizer
    JANOME_AVAILABLE = True
except ImportError:
    JANOME_AVAILABLE = False


@pytest.mark.skipif(not JANOME_AVAILABLE, reason="janome not installed")
class TestExtractNouns:
    @pytest.fixture
    def tokenizer(self):
        return Tokenizer()

    def test_extract_basic_nouns(self, tokenizer):
        nouns = extract_nouns("人工知能の最新動向を紹介", tokenizer)
        # janome splits "人工知能" into "人工" + "知能"
        assert "人工" in nouns or "知能" in nouns
        assert "最新" in nouns or "動向" in nouns

    def test_stop_nouns_excluded(self, tokenizer):
        nouns = extract_nouns("技術の活用方法を開発", tokenizer)
        for stop in ["技術", "活用", "方法", "開発"]:
            assert stop not in nouns

    def test_short_nouns_excluded(self, tokenizer):
        # Single character nouns should be excluded
        nouns = extract_nouns("日が昇る", tokenizer)
        assert "日" not in nouns


@pytest.mark.skipif(not JANOME_AVAILABLE, reason="janome not installed")
class TestComputeCooccurrence:
    @pytest.fixture
    def tokenizer(self):
        return Tokenizer()

    def test_basic_cooccurrence(self, tokenizer):
        titles = [
            "AI搭載のチャットボット登場",
            "AI活用した自然言語処理",
            "クラウドサービスの比較",
        ]
        results = compute_cooccurrence(titles, ["AI"], tokenizer)
        keywords = [r["keyword"] for r in results]
        # Should find nouns co-occurring with AI
        assert all(r["related_to"] == "AI" for r in results)
        assert all(r["source"] == "cooccurrence" for r in results)

    def test_no_match(self, tokenizer):
        titles = ["クラウドサービスの比較"]
        results = compute_cooccurrence(titles, ["AI"], tokenizer)
        assert results == []

    def test_keyword_itself_excluded(self, tokenizer):
        titles = ["AI技術のAI応用"]
        results = compute_cooccurrence(titles, ["AI"], tokenizer)
        keywords = [r["keyword"] for r in results]
        assert "AI" not in keywords


@pytest.mark.skipif(not JANOME_AVAILABLE, reason="janome not installed")
class TestAnalyzeCooccurrence:
    def test_with_valid_data(self, tmp_path):
        data = {
            "items": [
                {"title": "AI搭載のチャットボット"},
                {"title": "AI活用した音声認識"},
                {"title": "機械学習の基礎入門"},
            ],
        }
        path = str(tmp_path / "news.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        results = analyze_cooccurrence(path, ["AI"], min_frequency=1)
        assert isinstance(results, list)

    def test_empty_file(self, tmp_path):
        path = str(tmp_path / "empty.json")
        with open(path, "w") as f:
            json.dump({"items": []}, f)

        results = analyze_cooccurrence(path, ["AI"])
        assert results == []


class TestAnalyzeCooccurrenceWithoutJanome:
    @patch("src.keyword_optimizer.cooccurrence._JANOME_AVAILABLE", False)
    def test_returns_empty_without_janome(self, tmp_path):
        path = str(tmp_path / "news.json")
        with open(path, "w") as f:
            json.dump({"items": [{"title": "test"}]}, f)

        results = analyze_cooccurrence(path, ["AI"])
        assert results == []
