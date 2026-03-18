#!/usr/bin/env python3
"""
検索キーワード自動最適化スクリプト

はてブRSSトレンド + 過去ニュースの共起語分析で
config.py の NEWS_SEARCH_CONFIGS.synonyms を自動拡張する。

Usage:
    python scripts/optimize_keywords.py                    # 候補表示のみ（dry-run）
    python scripts/optimize_keywords.py --apply            # config.py更新
    python scripts/optimize_keywords.py --source hatena    # はてブのみ
    python scripts/optimize_keywords.py --max-synonyms 8   # synonyms上限指定

cron例:
    0 7 * * * /usr/bin/python3 /path/to/scripts/optimize_keywords.py --apply >> /path/to/logs/optimize.log 2>&1
"""

import argparse
import json
import logging
import os
import sys

# Project root setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.keyword_optimizer.cooccurrence import analyze_cooccurrence
from src.keyword_optimizer.config_writer import (
    backup_config,
    generate_config_content,
    load_config_module,
    save_suggestions,
    write_config,
)
from src.keyword_optimizer.hatena_collector import collect_trending_keywords
from src.keyword_optimizer.merger import merge_candidates

CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.py")
DATA_DIR = os.path.join(BASE_DIR, "data")
NEWS_JSON = os.path.join(DATA_DIR, "tech_news.json")
SUGGESTIONS_PATH = os.path.join(BASE_DIR, "config", "keyword_suggestions.json")

# Logging
logging.basicConfig(
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("optimize_keywords")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimize NEWS_SEARCH_CONFIGS synonyms automatically",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually update config.py (default: dry-run, output suggestions only)",
    )
    parser.add_argument(
        "--source",
        choices=["hatena", "cooccurrence", "all"],
        default="all",
        help="Which source to use for candidates (default: all)",
    )
    parser.add_argument(
        "--max-synonyms",
        type=int,
        default=10,
        help="Maximum synonyms per config entry (default: 10)",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=2,
        help="Minimum keyword frequency to consider (default: 2)",
    )
    return parser.parse_args()


def get_existing_keywords(configs: list[dict]) -> list[str]:
    """Extract all existing keywords from configs for co-occurrence analysis."""
    keywords: list[str] = []
    for cfg in configs:
        keywords.extend(cfg.get("keywords", []))
        keywords.extend(cfg.get("synonyms", []))
    return list(dict.fromkeys(keywords))  # Deduplicate preserving order


def collect_candidates(
    source: str,
    existing_keywords: list[str],
    min_frequency: int,
) -> list[dict]:
    """Collect keyword candidates from specified sources."""
    candidates: list[dict] = []

    if source in ("hatena", "all"):
        logger.info("Collecting from Hatena Bookmark...")
        hatena_candidates = collect_trending_keywords(min_frequency=min_frequency)
        candidates.extend(hatena_candidates)
        logger.info("Hatena: %d candidates", len(hatena_candidates))

    if source in ("cooccurrence", "all"):
        logger.info("Analyzing co-occurrence in past news...")
        cooccur_candidates = analyze_cooccurrence(
            json_path=NEWS_JSON,
            existing_keywords=existing_keywords,
            min_frequency=min_frequency,
        )
        candidates.extend(cooccur_candidates)
        logger.info("Co-occurrence: %d candidates", len(cooccur_candidates))

    return candidates


def main():
    args = parse_args()

    logger.info(
        "Start: source=%s, apply=%s, max_synonyms=%d, min_frequency=%d",
        args.source, args.apply, args.max_synonyms, args.min_frequency,
    )

    # 1. Load current config
    if not os.path.exists(CONFIG_PATH):
        logger.error("Config file not found: %s", CONFIG_PATH)
        sys.exit(1)

    config_module = load_config_module(CONFIG_PATH)
    current_configs = getattr(config_module, "NEWS_SEARCH_CONFIGS", None)
    if not current_configs:
        logger.error("NEWS_SEARCH_CONFIGS not found in config.py")
        sys.exit(1)

    logger.info("Current configs: %d entries", len(current_configs))

    # 2. Collect candidates
    existing_keywords = get_existing_keywords(current_configs)
    candidates = collect_candidates(args.source, existing_keywords, args.min_frequency)

    if not candidates:
        logger.info("No keyword candidates found")
        return

    logger.info("Total candidates: %d", len(candidates))

    # 3. Merge candidates into configs
    updated_configs, changes, new_genre_suggestions = merge_candidates(
        current_configs, candidates, max_synonyms=args.max_synonyms,
    )

    if not changes and not new_genre_suggestions:
        logger.info("No new synonyms to add and no new genre suggestions")
        return

    # Display synonym changes
    if changes:
        logger.info("=== Synonym additions ===")
        for change in changes:
            logger.info(
                "  + %s → %s (genre=%s, source=%s)",
                change["added"],
                change["keywords"],
                change["genre"] or "(person)",
                change["source"],
            )

    # Display new genre suggestions
    if new_genre_suggestions:
        logger.info("=== New genre suggestions (not auto-applied) ===")
        for suggestion in new_genre_suggestions:
            logger.info(
                "  * %s (freq=%d, source=%s)",
                suggestion["keyword"],
                suggestion["frequency"],
                suggestion["source"],
            )

    if not args.apply:
        # Dry-run: save suggestions JSON
        save_suggestions(SUGGESTIONS_PATH, candidates, changes, new_genre_suggestions)
        logger.info(
            "Dry-run: %d synonyms + %d new genre suggestions saved to %s",
            len(changes), len(new_genre_suggestions), SUGGESTIONS_PATH,
        )
        output = {
            "changes": changes,
            "new_genre_suggestions": new_genre_suggestions,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if not changes:
        logger.info("No synonym changes to apply (new genre suggestions are display-only)")
        return

    # 4. Apply: backup + write config
    with open(CONFIG_PATH, encoding="utf-8") as f:
        original_content = f.read()

    backup_path = backup_config(CONFIG_PATH)
    new_content = generate_config_content(original_content, updated_configs)

    try:
        write_config(CONFIG_PATH, new_content)
        logger.info(
            "OK: %d synonyms added, backup at %s",
            len(changes), backup_path,
        )
    except SyntaxError:
        logger.error("Generated config has syntax errors, rolling back")
        # Restore from backup
        import shutil
        shutil.copy2(backup_path, CONFIG_PATH)
        logger.info("Rolled back to: %s", backup_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
