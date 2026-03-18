#!/usr/bin/env python3
"""
ニュース自動取得スクリプト v3（ジャンル複合クエリ + ノイズフィルタリング）

Google News RSS + 直接RSS から日本語ニュースを取得し、
コンテンツフィルタ → 重複排除 → LLMフィルタ → WEB:YT割合制御 → 整形 → JSON保存。

Usage:
    python scripts/fetch_news.py               # 通常実行
    python scripts/fetch_news.py --dry-run      # 取得のみ、保存しない
    python scripts/fetch_news.py --no-llm       # LLMなしフォールバック
    python scripts/fetch_news.py --source google  # 特定ソースのみ

cron例:
    0 9,18 * * * /usr/bin/python3 /path/to/scripts/fetch_news.py >> /path/to/logs/news_fetch.log 2>&1
"""

import argparse
import logging
import os
import sys
from datetime import datetime

# Project root setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from config.config import (
    GOOGLE_NEWS_ENABLED,
    GOOGLE_NEWS_MAX_PER_GENRE,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    NEWS_DAYS,
    NEWS_MAX_ITEMS,
    RSS_FEEDS,
)

# Optional config values with defaults for backward compatibility
import config.config as _cfg

NEWS_SEARCH_CONFIGS = getattr(_cfg, "NEWS_SEARCH_CONFIGS", None)
NEWS_GENRES = getattr(_cfg, "NEWS_GENRES", "")
OUTPUT_WEB_RATIO = getattr(_cfg, "OUTPUT_WEB_RATIO", 7)
OUTPUT_YT_RATIO = getattr(_cfg, "OUTPUT_YT_RATIO", 3)
CONTENT_FILTER_ENABLED = getattr(_cfg, "CONTENT_FILTER_ENABLED", True)

from src.content_filter import ContentFilter
from src.dedup import ArticleDeduplicator
from src.formatter import NewsFormatter
from src.llm_filter import LLMFilter
from src.query_builder import SearchQuery, build_queries, build_queries_from_genres
from src.sources.base import RawArticle
from src.sources.google_news import GoogleNewsSource
from src.sources.rss_source import RssSource
from src.storage import NewsStorage
from src.validator import validate_news_items

DATA_DIR = os.path.join(BASE_DIR, "data")

# Logging
logging.basicConfig(
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("fetch_news")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and format news articles")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and format only, do not save",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Use keyword-based fallback instead of LLM",
    )
    parser.add_argument(
        "--source",
        choices=["google", "rss", "all"],
        default="all",
        help="Which source to use (default: all)",
    )
    return parser.parse_args()


def get_search_queries() -> list[SearchQuery]:
    """Build search queries from config, with fallback to legacy NEWS_GENRES."""
    if NEWS_SEARCH_CONFIGS:
        return build_queries(NEWS_SEARCH_CONFIGS)
    elif NEWS_GENRES:
        logger.info("Using legacy NEWS_GENRES fallback")
        return build_queries_from_genres(NEWS_GENRES)
    else:
        logger.warning("No search configuration found")
        return []


def fetch_articles(
    queries: list[SearchQuery],
    source_filter: str,
    max_per_query: int,
) -> list[RawArticle]:
    """Fetch articles from all enabled sources using SearchQuery objects."""
    articles: list[RawArticle] = []
    errors: list[str] = []

    # Google News RSS
    if source_filter in ("google", "all") and GOOGLE_NEWS_ENABLED:
        try:
            source = GoogleNewsSource(days=NEWS_DAYS)
            google_articles = source.fetch_by_queries(queries, max_per_query)
            articles.extend(google_articles)
            logger.info("Google News: %d articles total", len(google_articles))
        except Exception as e:
            errors.append(f"Google News: {e}")
            logger.exception("Google News source failed")

    # Direct RSS feeds (unchanged - genre matching is handled internally)
    if source_filter in ("rss", "all") and RSS_FEEDS:
        try:
            # Extract unique genre labels for RSS keyword matching
            genres = list(dict.fromkeys(q.genre_label for q in queries))
            source = RssSource(feeds=RSS_FEEDS)
            rss_articles = source.fetch(genres, max_per_query)
            articles.extend(rss_articles)
            logger.info("RSS: %d articles total", len(rss_articles))
        except Exception as e:
            errors.append(f"RSS: {e}")
            logger.exception("RSS source failed")

    if not articles and errors:
        raise RuntimeError(
            f"All sources failed: {'; '.join(errors)}"
        )

    return articles


def apply_mix_ratio(
    articles: list[RawArticle],
    web_ratio: int,
    yt_ratio: int,
    max_items: int,
) -> list[RawArticle]:
    """Apply WEB:YouTube mix ratio to article list.

    Args:
        articles: Ranked articles (already deduped/filtered)
        web_ratio: Target ratio for web articles (e.g. 7)
        yt_ratio: Target ratio for YouTube articles (e.g. 3)
        max_items: Total max output items

    Returns:
        Mixed list respecting the ratio, filling gaps from the other type.
    """
    web = [a for a in articles if a.content_type != "youtube"]
    yt = [a for a in articles if a.content_type == "youtube"]

    total_ratio = web_ratio + yt_ratio
    target_web = round(max_items * web_ratio / total_ratio)
    target_yt = max_items - target_web

    # Actual counts limited by availability
    actual_yt = min(len(yt), target_yt)
    actual_web = min(len(web), max_items - actual_yt)
    # If web couldn't fill, give extra slots to yt
    actual_yt = min(len(yt), max_items - actual_web)

    result = web[:actual_web] + yt[:actual_yt]

    logger.info(
        "Mix ratio: WEB %d/%d, YouTube %d/%d (target %d:%d)",
        actual_web, len(web), actual_yt, len(yt), web_ratio, yt_ratio,
    )

    return result


def fetch_and_format(
    queries: list[SearchQuery],
    source_filter: str = "all",
    use_llm: bool = True,
    max_items: int = NEWS_MAX_ITEMS,
    web_ratio: int = OUTPUT_WEB_RATIO,
    yt_ratio: int = OUTPUT_YT_RATIO,
    filter_enabled: bool = CONTENT_FILTER_ENABLED,
) -> list[dict]:
    """Main pipeline: query build -> fetch -> filter -> dedup -> LLM filter -> mix -> format -> validate."""
    max_per_query = GOOGLE_NEWS_MAX_PER_GENRE

    # 1. Fetch from all sources
    raw_articles = fetch_articles(queries, source_filter, max_per_query)
    logger.info("Total raw articles: %d", len(raw_articles))

    if not raw_articles:
        logger.warning("No articles fetched")
        return []

    # 2. Content filter (noise removal)
    if filter_enabled:
        content_filter = ContentFilter()
        filtered = content_filter.apply(raw_articles)
    else:
        filtered = raw_articles

    # 3. Deduplicate and rank
    deduplicator = ArticleDeduplicator()
    deduped = deduplicator.process(filtered, max_items=max_items * 2)
    logger.info("After dedup: %d articles", len(deduped))

    # 4. LLM relevance filter (optional)
    llm_provider = LLM_PROVIDER if use_llm else "none"
    if llm_provider == "openai" and LLM_API_KEY:
        llm_filter = LLMFilter(api_key=LLM_API_KEY, model=LLM_MODEL)
        deduped = llm_filter.filter(deduped)

    # 5. Apply WEB:YouTube mix ratio
    mixed = apply_mix_ratio(deduped, web_ratio, yt_ratio, max_items)

    # 6. Format with LLM or keyword fallback
    formatter = NewsFormatter(
        llm_provider=llm_provider,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
    )
    formatted = formatter.format(mixed)
    logger.info("Formatted: %d items", len(formatted))

    # 7. Validate
    validated = validate_news_items(formatted)
    logger.info("Validated: %d items", len(validated))

    return validated[:max_items]


def main():
    args = parse_args()

    # Build search queries
    queries = get_search_queries()
    if not queries:
        logger.error("No search queries configured")
        sys.exit(1)

    logger.info(
        "Start: %d queries, source=%s, dry_run=%s, no_llm=%s",
        len(queries), args.source, args.dry_run, args.no_llm,
    )

    try:
        # Run pipeline
        items = fetch_and_format(
            queries=queries,
            source_filter=args.source,
            use_llm=not args.no_llm,
            max_items=NEWS_MAX_ITEMS,
        )

        if not items:
            logger.error("No articles produced")
            sys.exit(1)

        # Display results
        for item in items:
            logger.info(
                "  [%s] %s - %s (%s) [%s]",
                item["category"],
                item["date"],
                item["title"],
                item["source"],
                item["type"],
            )

        if args.dry_run:
            logger.info("Dry run: %d items (not saved)", len(items))
            import json
            print(json.dumps(items, ensure_ascii=False, indent=2))
            return

        # Save
        storage = NewsStorage(data_dir=DATA_DIR)
        storage.backup()
        saved_path = storage.save(items, max_items=NEWS_MAX_ITEMS)
        logger.info("OK: %d articles saved to %s", len(items), saved_path)

    except Exception as e:
        logger.error("ERROR: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
