"""Tests for news item validation."""

import pytest

from src.validator import validate_news_items


class TestValidateNewsItems:
    def test_valid_items(self):
        items = [
            {
                "title": "AIの最新動向",
                "link": "https://example.com/1",
                "date": "2026-03-15",
                "category": "AI",
                "source": "ITmedia",
                "type": "article",
            }
        ]
        result = validate_news_items(items)
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["title"] == "AIの最新動向"
        assert result[0]["auto_generated"] is True

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="empty"):
            validate_news_items([])

    def test_invalid_category_defaults(self):
        items = [
            {
                "title": "テスト記事",
                "link": "https://example.com/1",
                "date": "2026-03-15",
                "category": "無効なカテゴリ",
            }
        ]
        result = validate_news_items(items)
        assert result[0]["category"] == "テクノロジー"

    def test_invalid_date_defaults_to_today(self):
        items = [
            {
                "title": "テスト記事",
                "link": "https://example.com/1",
                "date": "invalid-date",
                "category": "AI",
            }
        ]
        result = validate_news_items(items)
        # Should be a valid date format
        assert len(result[0]["date"]) == 10

    def test_long_title_truncated(self):
        items = [
            {
                "title": "あ" * 150,
                "link": "https://example.com/1",
                "date": "2026-03-15",
            }
        ]
        result = validate_news_items(items)
        assert len(result[0]["title"]) <= 100

    def test_invalid_link_skipped(self):
        items = [
            {
                "title": "有効な記事",
                "link": "https://example.com/valid",
                "date": "2026-03-15",
            },
            {
                "title": "無効リンク記事",
                "link": "not-a-url",
                "date": "2026-03-15",
            },
        ]
        result = validate_news_items(items)
        assert len(result) == 1
        assert result[0]["title"] == "有効な記事"

    def test_empty_title_skipped(self):
        items = [
            {
                "title": "",
                "link": "https://example.com/1",
                "date": "2026-03-15",
            },
            {
                "title": "有効な記事",
                "link": "https://example.com/2",
                "date": "2026-03-15",
            },
        ]
        result = validate_news_items(items)
        assert len(result) == 1

    def test_youtube_type_preserved(self):
        items = [
            {
                "title": "動画記事",
                "link": "https://youtube.com/watch?v=abc",
                "date": "2026-03-15",
                "type": "youtube",
            }
        ]
        result = validate_news_items(items)
        assert result[0]["type"] == "youtube"

    def test_ids_are_sequential(self):
        items = [
            {"title": f"記事{i}", "link": f"https://example.com/{i}", "date": "2026-03-15"}
            for i in range(5)
        ]
        result = validate_news_items(items)
        ids = [item["id"] for item in result]
        assert ids == [1, 2, 3, 4, 5]

    def test_all_invalid_raises(self):
        items = [
            {"title": "", "link": "not-url"},
            {"title": "", "link": "also-not-url"},
        ]
        with pytest.raises(ValueError, match="No valid items"):
            validate_news_items(items)
