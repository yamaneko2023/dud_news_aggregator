"""Tests for LLM relevance filter."""

import json
import sys
from unittest.mock import MagicMock, patch

from src.llm_filter import LLMFilter
from src.sources.base import RawArticle


def _make_article(title: str = "テスト記事", index: int = 1) -> RawArticle:
    return RawArticle(
        title=title,
        url=f"https://example.com/article{index}",
        published_date="2026-03-15",
        source_name="TestSource",
        content_snippet="テスト内容",
        content_type="article",
        genre_query="AI",
    )


def _mock_openai_module(response_content):
    """Create a mock openai module that returns the given response content."""
    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_openai.OpenAI.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = response_content
    mock_client.chat.completions.create.return_value = mock_response

    return mock_openai, mock_client


class TestLLMFilter:
    def test_no_api_key_passes_all(self):
        """Without API key, all articles pass through."""
        f = LLMFilter(api_key="")
        articles = [_make_article("記事1", 1), _make_article("記事2", 2)]
        result = f.filter(articles)
        assert len(result) == 2

    def test_empty_list(self):
        f = LLMFilter(api_key="test-key")
        result = f.filter([])
        assert result == []

    def test_filters_by_relevance(self):
        """LLM marks some articles as irrelevant."""
        mock_openai, mock_client = _mock_openai_module(
            json.dumps({
                "results": [
                    {"index": 1, "relevant": True},
                    {"index": 2, "relevant": False},
                ]
            })
        )

        with patch.dict(sys.modules, {"openai": mock_openai}):
            f = LLMFilter(api_key="test-key")
            articles = [_make_article("テック記事", 1), _make_article("ノイズ記事", 2)]
            result = f.filter(articles)

        assert len(result) == 1
        assert result[0].title == "テック記事"

    def test_fail_open_on_api_error(self):
        """On API error, all articles pass through."""
        mock_openai = MagicMock()
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")

        with patch.dict(sys.modules, {"openai": mock_openai}):
            f = LLMFilter(api_key="test-key")
            articles = [_make_article("記事1", 1), _make_article("記事2", 2)]
            result = f.filter(articles)

        assert len(result) == 2

    def test_fail_open_on_empty_response(self):
        """On empty LLM response, all articles pass through."""
        mock_openai, _ = _mock_openai_module(None)

        with patch.dict(sys.modules, {"openai": mock_openai}):
            f = LLMFilter(api_key="test-key")
            articles = [_make_article("記事1", 1)]
            result = f.filter(articles)

        assert len(result) == 1

    def test_fail_open_on_empty_results(self):
        """On empty results array, all articles pass through."""
        mock_openai, _ = _mock_openai_module(json.dumps({"results": []}))

        with patch.dict(sys.modules, {"openai": mock_openai}):
            f = LLMFilter(api_key="test-key")
            articles = [_make_article("記事1", 1)]
            result = f.filter(articles)

        assert len(result) == 1
