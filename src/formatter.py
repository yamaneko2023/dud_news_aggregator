"""News formatting with LLM (OpenAI gpt-4o-mini) or keyword-based fallback."""

from __future__ import annotations

import json
import logging
import re

from .sources.base import RawArticle

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "AI": [
        "ai", "人工知能", "機械学習", "深層学習", "ディープラーニング",
        "llm", "大規模言語モデル", "gpt", "claude", "gemini", "chatgpt",
        "生成ai", "生成ＡＩ", "openai", "anthropic",
    ],
    "DX": [
        "dx", "デジタルトランスフォーメーション", "デジタル変革", "自動化",
        "rpa", "業務効率", "ローコード", "ノーコード",
    ],
    "データ": [
        "データ", "ビッグデータ", "データ分析", "データサイエンス",
        "bigquery", "データベース", "sql", "データ基盤",
    ],
}

LLM_SYSTEM_PROMPT = """\
あなたはニュース記事のメタデータを整形するアシスタントです。
与えられた記事リストを指定のJSON形式に変換してください。

ルール:
- titleは日本語で50文字以内に要約（元が日本語ならそのまま短縮）
- categoryは "AI", "DX", "データ", "テクノロジー" のいずれか
- sourceは元記事のソース名をそのまま使用
- typeは "article" または "youtube"
- 必ず有効なJSONオブジェクトとして返すこと（マークダウンで囲まないこと）
"""

LLM_USER_TEMPLATE = """\
以下の記事リストをJSON形式に変換してください。

入力記事:
{articles_text}

出力形式（JSON object）:
{{
  "items": [
    {{
      "date": "YYYY-MM-DD",
      "category": "AI | DX | データ | テクノロジー",
      "title": "日本語タイトル（50文字以内）",
      "link": "URL",
      "source": "ソース名",
      "type": "article | youtube"
    }}
  ]
}}
"""


class NewsFormatter:
    """Format raw articles into the final output schema."""

    def __init__(
        self,
        llm_provider: str = "none",
        api_key: str = "",
        model: str = "gpt-4o-mini",
    ):
        self.llm_provider = llm_provider
        self.api_key = api_key
        self.model = model

    def format(self, articles: list[RawArticle]) -> list[dict]:
        """Format articles into output dicts."""
        if not articles:
            return []

        if self.llm_provider == "openai" and self.api_key:
            try:
                return self._format_with_llm(articles)
            except Exception:
                logger.exception("LLM formatting failed, using fallback")

        return self._format_keyword_based(articles)

    def _format_with_llm(self, articles: list[RawArticle]) -> list[dict]:
        """Use OpenAI gpt-4o-mini with JSON mode."""
        import openai

        articles_text = self._build_articles_text(articles)

        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": LLM_USER_TEMPLATE.format(
                        articles_text=articles_text
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=4000,
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Empty LLM response")

        data = json.loads(content)
        items = data.get("items", [])

        if not items:
            raise RuntimeError("LLM returned empty items")

        # Merge URLs from original articles (LLM might alter them)
        url_map = {a.title[:30]: a for a in articles}
        for item in items:
            # Try to match back to original for reliable URL
            for key, orig in url_map.items():
                if key in item.get("title", ""):
                    item["link"] = orig.url
                    break

        logger.info("LLM formatted %d items", len(items))
        return items

    def _format_keyword_based(self, articles: list[RawArticle]) -> list[dict]:
        """Keyword-based fallback formatting (no LLM needed)."""
        results: list[dict] = []

        for article in articles:
            category = self._classify_category(article)
            title = self._truncate_title(article.title, 50)

            results.append({
                "date": article.published_date,
                "category": category,
                "title": title,
                "link": article.url,
                "source": article.source_name,
                "type": article.content_type,
            })

        logger.info("Keyword-based formatted %d items", len(results))
        return results

    @staticmethod
    def _classify_category(article: RawArticle) -> str:
        """Classify article into category based on keywords."""
        text = (
            article.title + " " + article.content_snippet + " " + article.genre_query
        ).lower()

        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return category

        return "テクノロジー"

    @staticmethod
    def _truncate_title(title: str, max_len: int) -> str:
        """Truncate title to max_len characters."""
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) <= max_len:
            return title
        return title[: max_len - 1] + "…"

    @staticmethod
    def _build_articles_text(articles: list[RawArticle]) -> str:
        lines: list[str] = []
        for i, a in enumerate(articles, 1):
            lines.append(
                f"{i}. [{a.published_date}] {a.title}\n"
                f"   URL: {a.url}\n"
                f"   Source: {a.source_name}\n"
                f"   Type: {a.content_type}\n"
                f"   Snippet: {a.content_snippet[:100]}"
            )
        return "\n\n".join(lines)
