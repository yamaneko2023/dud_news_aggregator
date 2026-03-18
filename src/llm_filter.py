"""LLM-based relevance filter using gpt-4o-mini batch judgment."""

from __future__ import annotations

import json
import logging

from .sources.base import RawArticle

logger = logging.getLogger(__name__)

LLM_FILTER_SYSTEM_PROMPT = """\
あなたはテクノロジーニュースの関連度を判定するアシスタントです。
与えられた記事リストについて、各記事がテック系ニュースとして適切かを判定してください。

判定基準:
- 適切: IT、AI、ソフトウェア、ハードウェア、クラウド、データ、DX等に関する記事
- 不適切: エンタメ、アニメ、ゲーム（テック文脈除く）、芸能、スポーツ等

必ず有効なJSONオブジェクトとして返してください。
"""

LLM_FILTER_USER_TEMPLATE = """\
以下の記事リストについて、各記事がテック系ニュースとして適切か判定してください。

{articles_text}

出力形式（JSON object）:
{{
  "results": [
    {{"index": 1, "relevant": true}},
    {{"index": 2, "relevant": false}}
  ]
}}
"""


class LLMFilter:
    """Filter articles by tech relevance using LLM batch judgment."""

    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def filter(self, articles: list[RawArticle]) -> list[RawArticle]:
        """Filter articles using LLM. Fail-open: returns all on error."""
        if not articles:
            return []

        if not self.api_key:
            logger.info("LLM filter: no API key, skipping (pass-through)")
            return articles

        try:
            return self._filter_with_llm(articles)
        except Exception:
            logger.exception("LLM filter failed, passing all articles through (fail-open)")
            return articles

    def _filter_with_llm(self, articles: list[RawArticle]) -> list[RawArticle]:
        import openai

        articles_text = self._build_articles_text(articles)

        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": LLM_FILTER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": LLM_FILTER_USER_TEMPLATE.format(
                        articles_text=articles_text
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=2000,
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Empty LLM response")

        data = json.loads(content)
        results = data.get("results", [])

        if not results:
            logger.warning("LLM filter returned empty results, passing all through")
            return articles

        # Build relevance map (1-indexed)
        relevant_set = set()
        for r in results:
            if r.get("relevant", True):
                relevant_set.add(r.get("index", 0))

        filtered = []
        removed_count = 0
        for i, article in enumerate(articles, 1):
            if i in relevant_set:
                filtered.append(article)
            else:
                removed_count += 1
                logger.debug("LLM filter removed: %s", article.title[:50])

        logger.info(
            "LLM filter: %d -> %d articles (%d removed)",
            len(articles),
            len(filtered),
            removed_count,
        )
        return filtered

    @staticmethod
    def _build_articles_text(articles: list[RawArticle]) -> str:
        lines: list[str] = []
        for i, a in enumerate(articles, 1):
            lines.append(
                f"{i}. {a.title}\n"
                f"   Source: {a.source_name} | Type: {a.content_type}\n"
                f"   Snippet: {a.content_snippet[:80]}"
            )
        return "\n\n".join(lines)
