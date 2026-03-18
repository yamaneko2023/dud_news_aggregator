"""Build composite search queries from NEWS_SEARCH_CONFIGS."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """A single search query to send to Google News RSS."""

    query: str  # e.g. "テクノロジー AI -ラブライブ"
    genre_label: str  # e.g. "AI" (set on RawArticle.genre_query)
    source_type: str  # "web" or "youtube"


def build_queries(search_configs: list[dict]) -> list[SearchQuery]:
    """Generate SearchQuery list from NEWS_SEARCH_CONFIGS.

    For each config entry, generates:
    - WEB queries: genre + keyword (+ synonyms) with excludes
    - YouTube queries: genre + keyword (main keywords only) with excludes

    Args:
        search_configs: List of config dicts with keys:
            genre, keywords, synonyms, exclude, youtube

    Returns:
        List of SearchQuery objects
    """
    queries: list[SearchQuery] = []

    for config in search_configs:
        genre = config.get("genre", "")
        keywords = config.get("keywords", [])
        synonyms = config.get("synonyms", [])
        excludes = config.get("exclude", [])
        youtube_enabled = config.get("youtube", True)

        exclude_part = " ".join(f"-{e}" for e in excludes)

        # WEB queries: main keywords + synonyms
        all_web_terms = keywords + synonyms
        for term in all_web_terms:
            genre_label = keywords[0] if keywords else term
            q = _build_query_string(genre, term, exclude_part)
            queries.append(SearchQuery(
                query=q,
                genre_label=genre_label,
                source_type="web",
            ))

        # YouTube queries: main keywords only
        if youtube_enabled:
            for kw in keywords:
                genre_label = kw
                q = _build_query_string(genre, kw, exclude_part)
                queries.append(SearchQuery(
                    query=q,
                    genre_label=genre_label,
                    source_type="youtube",
                ))

    logger.info("Built %d queries (web + youtube)", len(queries))
    return queries


def build_queries_from_genres(genres_str: str) -> list[SearchQuery]:
    """Fallback: convert legacy NEWS_GENRES string to SearchQuery list.

    Each genre becomes a simple web + youtube query without genre prefix or excludes.
    """
    genres = [g.strip() for g in genres_str.split(",") if g.strip()]
    queries: list[SearchQuery] = []

    for genre in genres:
        queries.append(SearchQuery(
            query=genre,
            genre_label=genre,
            source_type="web",
        ))
        queries.append(SearchQuery(
            query=genre,
            genre_label=genre,
            source_type="youtube",
        ))

    return queries


def _build_query_string(genre: str, keyword: str, exclude_part: str) -> str:
    """Assemble query string from parts."""
    parts = []
    if genre:
        parts.append(genre)
    parts.append(keyword)
    if exclude_part:
        parts.append(exclude_part)
    return " ".join(parts)
