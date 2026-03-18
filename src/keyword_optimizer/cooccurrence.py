"""Co-occurrence analysis on past news titles using janome tokenizer."""

import json
import logging
import os
from collections import Counter

logger = logging.getLogger(__name__)

# Try importing janome; skip gracefully if not installed
try:
    from janome.tokenizer import Tokenizer

    _JANOME_AVAILABLE = True
except ImportError:
    _JANOME_AVAILABLE = False
    logger.warning("janome is not installed; co-occurrence analysis will be skipped")


# Minimum noun length to consider
MIN_NOUN_LEN = 2

# Nouns to exclude (too generic)
STOP_NOUNS = frozenset({
    "こと", "もの", "ため", "それ", "これ", "よう", "ところ",
    "ほう", "とき", "まとめ", "記事", "話題", "情報", "技術",
    "方法", "結果", "理由", "問題", "対応", "利用", "開発",
    "発表", "公開", "提供", "搭載", "対象", "活用",
})


def load_past_titles(json_path: str) -> list[str]:
    """Load article titles from tech_news.json.

    Supports both wrapper format {"items": [...]} and raw list format.
    """
    if not os.path.exists(json_path):
        logger.warning("News file not found: %s", json_path)
        return []

    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load %s: %s", json_path, e)
        return []

    if isinstance(data, dict) and "items" in data:
        items = data["items"]
    elif isinstance(data, list):
        items = data
    else:
        return []

    return [item["title"] for item in items if isinstance(item, dict) and "title" in item]


def extract_nouns(text: str, tokenizer) -> list[str]:
    """Extract nouns from text using janome tokenizer."""
    nouns = []
    for token in tokenizer.tokenize(text):
        parts = token.part_of_speech.split(",")
        if parts[0] == "名詞" and parts[1] in ("一般", "固有名詞", "サ変接続"):
            surface = token.surface
            if len(surface) >= MIN_NOUN_LEN and surface not in STOP_NOUNS:
                nouns.append(surface)
    return nouns


def compute_cooccurrence(
    titles: list[str],
    target_keywords: list[str],
    tokenizer,
) -> list[dict]:
    """Compute co-occurrence scores between target keywords and nouns in titles.

    For each title, if it contains any of the target keywords (case-insensitive),
    extract nouns and count co-occurrences.

    Args:
        titles: List of article titles.
        target_keywords: Keywords to check co-occurrence with (from existing config).
        tokenizer: janome Tokenizer instance.

    Returns:
        List of {"keyword": str, "cooccurrence_score": float,
                 "related_to": str, "source": "cooccurrence"}
        sorted by score desc.
    """
    # keyword -> co-occurring noun counter
    cooccur: dict[str, Counter] = {kw: Counter() for kw in target_keywords}

    target_lower = {kw: kw.lower() for kw in target_keywords}

    for title in titles:
        title_lower = title.lower()
        matched_keywords = [
            kw for kw, kw_l in target_lower.items()
            if kw_l in title_lower
        ]
        if not matched_keywords:
            continue

        nouns = extract_nouns(title, tokenizer)
        for kw in matched_keywords:
            for noun in nouns:
                # Skip if noun is the keyword itself
                if noun.lower() == kw.lower():
                    continue
                cooccur[kw][noun] += 1

    # Flatten results
    results = []
    seen_keywords: set[str] = set()
    for kw, counter in cooccur.items():
        for noun, count in counter.most_common():
            if noun not in seen_keywords:
                results.append({
                    "keyword": noun,
                    "cooccurrence_score": float(count),
                    "related_to": kw,
                    "source": "cooccurrence",
                })
                seen_keywords.add(noun)

    results.sort(key=lambda x: x["cooccurrence_score"], reverse=True)
    return results


def analyze_cooccurrence(
    json_path: str,
    existing_keywords: list[str],
    min_frequency: int = 2,
) -> list[dict]:
    """Main entry point for co-occurrence analysis.

    Args:
        json_path: Path to tech_news.json.
        existing_keywords: Keywords from current config to find co-occurrences for.
        min_frequency: Minimum co-occurrence count to include.

    Returns:
        List of keyword candidates with co-occurrence scores.
        Empty list if janome is not available.
    """
    if not _JANOME_AVAILABLE:
        logger.warning("Skipping co-occurrence analysis (janome not installed)")
        return []

    titles = load_past_titles(json_path)
    if not titles:
        logger.info("No past titles found for co-occurrence analysis")
        return []

    tokenizer = Tokenizer()
    results = compute_cooccurrence(titles, existing_keywords, tokenizer)

    # Filter by minimum frequency
    results = [r for r in results if r["cooccurrence_score"] >= min_frequency]

    logger.info(
        "Co-occurrence analysis: %d candidates from %d titles",
        len(results), len(titles),
    )
    return results
