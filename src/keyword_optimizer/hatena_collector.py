"""Collect trending tech keywords from Hatena Bookmark IT hotentry RSS."""

from __future__ import annotations

import logging
import re
from collections import Counter

import feedparser

logger = logging.getLogger(__name__)

HATENA_IT_RSS = "http://b.hatena.ne.jp/hotentry/it.rss"

# Common words to exclude from keyword extraction
STOP_WORDS = frozenset({
    # Japanese generic
    "こと", "もの", "ため", "それ", "これ", "あれ", "ここ", "そこ",
    "よう", "ところ", "ほう", "とき", "やつ", "まとめ",
    # Tech generic (too broad)
    "サービス", "システム", "アプリ", "プログラム", "ソフト",
    "ツール", "プロジェクト", "エンジニア", "データ", "コード",
    "テスト", "サーバー", "ネットワーク", "セキュリティ",
    # Japanese: too generic (actions/states)
    "リリース", "アップデート", "バージョン", "インストール",
    "ダウンロード", "レビュー", "ランキング",
    "チェック", "ニュース",
    # English generic
    "the", "and", "for", "with", "from", "that", "this", "are",
    "was", "has", "have", "how", "what", "why", "new", "can",
    "use", "not", "you", "all", "get", "web", "app", "api",
    # English: too generic or company/platform names (lowercase for .lower() comparison)
    "code", "google", "apple", "microsoft", "amazon", "meta",
    "linux", "windows", "mac", "java", "python", "ruby",
    "go", "php", "css", "html", "sql",
    # Site/blog names (lowercase for .lower() comparison)
    "developersio", "qiita", "zenn", "github", "gitlab",
    "hatena", "techcrunch", "publickey", "gigazine",
})

# Minimum keyword length
MIN_KEYWORD_LEN = 2

# Regex patterns for tech keyword extraction
# Note: \b doesn't work at Japanese/ASCII boundaries, so we use (?<![A-Za-z]) / (?![A-Za-z])
ENGLISH_TECH_RE = re.compile(
    r"(?<![A-Za-z0-9])"       # not preceded by alphanumeric
    r"[A-Z][A-Za-z0-9]*"      # starts with uppercase
    r"(?:[-_.][A-Za-z0-9]+)*"  # optional hyphenated parts (e.g. GPT-4o)
    r"(?![A-Za-z0-9])"        # not followed by alphanumeric
)
KATAKANA_RE = re.compile(r"[ァ-ヶー]{3,}")  # e.g. クラウド, コンテナ


def fetch_hatena_entries(rss_url: str = HATENA_IT_RSS) -> list[dict]:
    """Fetch entries from Hatena Bookmark IT RSS.

    Returns:
        List of {"title": str, "link": str} dicts.
    """
    feed = feedparser.parse(rss_url)
    if feed.bozo and not feed.entries:
        logger.warning("Failed to parse Hatena RSS: %s", feed.bozo_exception)
        return []

    entries = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        if title:
            entries.append({"title": title, "link": link})

    logger.info("Fetched %d entries from Hatena Bookmark", len(entries))
    return entries


def extract_keywords_from_titles(titles: list[str]) -> Counter:
    """Extract tech keywords from titles using regex patterns.

    Extracts:
    - CamelCase words (e.g. ChatGPT, GitHub)
    - Uppercase tech terms (e.g. LLM, GPT-4, AWS)
    - Katakana words 3+ chars (e.g. クラウド, コンテナ)
    """
    counter: Counter = Counter()

    for title in titles:
        found: set[str] = set()

        # English tech terms (e.g. AI, LLM, ChatGPT, GPT-4o)
        for m in ENGLISH_TECH_RE.finditer(title):
            word = m.group()
            if len(word) >= MIN_KEYWORD_LEN and word.lower() not in STOP_WORDS:
                found.add(word)

        # Katakana words (e.g. クラウド, コンテナ)
        for m in KATAKANA_RE.finditer(title):
            word = m.group()
            if word not in STOP_WORDS:
                found.add(word)

        counter.update(found)

    return counter


def collect_trending_keywords(
    min_frequency: int = 2,
    rss_url: str = HATENA_IT_RSS,
) -> list[dict]:
    """Collect trending tech keywords from Hatena Bookmark.

    Args:
        min_frequency: Minimum occurrence count to include.
        rss_url: RSS feed URL.

    Returns:
        List of {"keyword": str, "frequency": int, "source": "hatena"} sorted by frequency desc.
    """
    entries = fetch_hatena_entries(rss_url)
    if not entries:
        return []

    titles = [e["title"] for e in entries]
    counter = extract_keywords_from_titles(titles)

    results = []
    for keyword, freq in counter.most_common():
        if freq >= min_frequency:
            results.append({
                "keyword": keyword,
                "frequency": freq,
                "source": "hatena",
            })

    logger.info(
        "Extracted %d trending keywords (min_freq=%d)",
        len(results), min_frequency,
    )
    return results
