"""Content filtering: noise patterns, domain blacklist, tech co-occurrence check."""

import logging
import re
from urllib.parse import urlparse

from .sources.base import RawArticle

logger = logging.getLogger(__name__)

# Noise patterns in title/snippet (regex)
NOISE_PATTERNS = [
    r"踊ってみた",
    r"歌ってみた",
    r"ラブライブ",
    r"ガチャ",
    r"プリキュア",
    r"ウマ娘",
    r"声優",
    r"ホロライブ",
    r"にじさんじ",
    r"Vtuber",
    r"vtuber",
    r"推し活",
    r"ライブ配信.*(歌|踊)",
]

# Domain blacklist (non-tech entertainment sites)
DOMAIN_BLACKLIST = [
    "pixiv.net",
    "nicovideo.jp",
    "nico.ms",
    "tiktok.com",
    "showroom-live.com",
    "fantia.jp",
    "dlsite.com",
]

# Tech co-occurrence keywords: if an article matches an ambiguous keyword (e.g. "AI"),
# at least one of these must appear in title+snippet to pass
TECH_COOCCURRENCE_WORDS = [
    "機械学習", "開発", "エンジニア", "プログラミング", "テクノロジー",
    "claude", "gpt", "openai", "anthropic", "google", "microsoft",
    "企業", "導入", "活用", "サービス", "プロダクト", "ソフトウェア",
    "api", "モデル", "データ", "アルゴリズム", "自動化", "ロボット",
    "研究", "論文", "学習", "推論", "生成", "chatbot", "チャットボット",
    "llm", "大規模言語", "深層学習", "ディープラーニング",
    "ニューラル", "transformer", "gpu", "半導体", "クラウド",
    "スタートアップ", "it", "テック", "デジタル", "dx",
    "セキュリティ", "サイバー", "ブロックチェーン", "web3",
]

# Keywords considered ambiguous (might match non-tech content)
AMBIGUOUS_KEYWORDS = {"ai", "人工知能", "ロボット", "自動化"}

# Keywords that are specific enough to skip co-occurrence check
# (set automatically: anything NOT in AMBIGUOUS_KEYWORDS)


class ContentFilter:
    """Three-stage content filter for noise removal."""

    def __init__(
        self,
        noise_patterns: list[str] | None = None,
        domain_blacklist: list[str] | None = None,
        cooccurrence_words: list[str] | None = None,
        ambiguous_keywords: set[str] | None = None,
    ):
        self.noise_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (noise_patterns or NOISE_PATTERNS)
        ]
        self.domain_blacklist = domain_blacklist or DOMAIN_BLACKLIST
        self.cooccurrence_words = [
            w.lower() for w in (cooccurrence_words or TECH_COOCCURRENCE_WORDS)
        ]
        self.ambiguous_keywords = ambiguous_keywords or AMBIGUOUS_KEYWORDS

    def apply(self, articles: list[RawArticle]) -> list[RawArticle]:
        """Apply all filters and return filtered list."""
        initial_count = len(articles)
        stats = {"noise_pattern": 0, "domain": 0, "cooccurrence": 0}

        result: list[RawArticle] = []
        for article in articles:
            reason = self._should_exclude(article)
            if reason:
                stats[reason] += 1
                logger.debug("Excluded [%s]: %s", reason, article.title[:50])
            else:
                result.append(article)

        removed = initial_count - len(result)
        logger.info(
            "ContentFilter: %d -> %d articles "
            "(noise_pattern: -%d, domain: -%d, cooccurrence: -%d)",
            initial_count,
            len(result),
            stats["noise_pattern"],
            stats["domain"],
            stats["cooccurrence"],
        )

        return result

    def _should_exclude(self, article: RawArticle) -> str | None:
        """Return exclusion reason or None if article passes all filters."""
        text = article.title + " " + article.content_snippet

        # 1. Noise pattern check
        for pattern in self.noise_patterns:
            if pattern.search(text):
                return "noise_pattern"

        # 2. Domain blacklist (YouTube is never blacklisted)
        if article.content_type != "youtube":
            domain = self._extract_domain(article.url)
            for blocked in self.domain_blacklist:
                if blocked in domain:
                    return "domain"

        # 3. Tech co-occurrence check (only for ambiguous keywords)
        if self._is_ambiguous_query(article.genre_query):
            if not self._has_tech_cooccurrence(text):
                return "cooccurrence"

        return None

    def _is_ambiguous_query(self, genre_query: str) -> bool:
        """Check if the genre_query is an ambiguous keyword."""
        return genre_query.lower() in self.ambiguous_keywords

    def _has_tech_cooccurrence(self, text: str) -> bool:
        """Check if text contains at least one tech co-occurrence word."""
        text_lower = text.lower()
        return any(word in text_lower for word in self.cooccurrence_words)

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""
