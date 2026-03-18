"""Article deduplication and ranking."""

import unicodedata
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .sources.base import RawArticle


class ArticleDeduplicator:
    """Remove duplicate articles and rank by freshness + genre diversity."""

    TITLE_SIMILARITY_THRESHOLD = 0.6

    def process(
        self, articles: list[RawArticle], max_items: int = 10
    ) -> list[RawArticle]:
        """Deduplicate and rank articles.

        1. URL-based exact dedup
        2. Title similarity fuzzy dedup (Jaccard coefficient)
        3. Rank by freshness + genre diversity
        """
        if not articles:
            return []

        # Step 1: URL dedup
        url_deduped = self._dedup_by_url(articles)

        # Step 2: Title similarity dedup
        title_deduped = self._dedup_by_title(url_deduped)

        # Step 3: Rank
        ranked = self._rank(title_deduped)

        return ranked[:max_items]

    def _dedup_by_url(self, articles: list[RawArticle]) -> list[RawArticle]:
        seen_urls: set[str] = set()
        result: list[RawArticle] = []

        for article in articles:
            normalized = self._normalize_url(article.url)
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                result.append(article)

        return result

    def _dedup_by_title(self, articles: list[RawArticle]) -> list[RawArticle]:
        result: list[RawArticle] = []

        for article in articles:
            normalized_title = self._normalize_text(article.title)
            title_tokens = self._tokenize(normalized_title)

            is_duplicate = False
            for existing in result:
                existing_tokens = self._tokenize(
                    self._normalize_text(existing.title)
                )
                similarity = self._jaccard_similarity(title_tokens, existing_tokens)
                if similarity >= self.TITLE_SIMILARITY_THRESHOLD:
                    is_duplicate = True
                    break

            if not is_duplicate:
                result.append(article)

        return result

    def _rank(self, articles: list[RawArticle]) -> list[RawArticle]:
        """Rank by date (newer first) + genre diversity bonus."""
        today = datetime.now().strftime("%Y-%m-%d")
        genre_counts: dict[str, int] = {}

        scored: list[tuple[float, RawArticle]] = []
        for article in articles:
            # Freshness score: newer = higher
            freshness = self._freshness_score(article.published_date, today)

            # Genre diversity: penalize overrepresented genres
            genre = article.genre_query
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
            diversity_penalty = (genre_counts[genre] - 1) * 0.1

            score = freshness - diversity_penalty + article.score
            scored.append((score, article))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [article for _, article in scored]

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL by removing query parameters and fragments.

        Exception: YouTube watch URLs preserve the 'v' parameter since it
        identifies the video.
        """
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc and parsed.path == "/watch":
            params = parse_qs(parsed.query)
            if "v" in params:
                preserved = urlencode({"v": params["v"][0]})
                return urlunparse(
                    (parsed.scheme, parsed.netloc, parsed.path, "", preserved, "")
                )
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, "", "", "")
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        """NFKC normalize and lowercase."""
        return unicodedata.normalize("NFKC", text).lower().strip()

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Simple character bigram tokenizer for Japanese text."""
        text = text.replace(" ", "").replace("\u3000", "")
        if len(text) < 2:
            return {text}
        return {text[i : i + 2] for i in range(len(text) - 1)}

    @staticmethod
    def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _freshness_score(date_str: str, today: str) -> float:
        """Score 0.0-1.0 based on how recent the article is."""
        try:
            article_date = datetime.strptime(date_str, "%Y-%m-%d")
            today_date = datetime.strptime(today, "%Y-%m-%d")
            days_old = (today_date - article_date).days
            if days_old < 0:
                days_old = 0
            return max(0.0, 1.0 - days_old * 0.1)
        except ValueError:
            return 0.5
