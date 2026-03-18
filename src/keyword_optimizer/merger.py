"""Merge new keyword candidates into existing NEWS_SEARCH_CONFIGS."""

import logging

logger = logging.getLogger(__name__)


def _is_person_entry(config: dict) -> bool:
    """Check if a config entry is for a person name (genre="" + Japanese name)."""
    if config.get("genre"):
        return False
    keywords = config.get("keywords", [])
    # Heuristic: person entry has genre="" and keywords contain Japanese characters
    for kw in keywords:
        if any("\u3040" <= c <= "\u9fff" for c in kw):
            return True
    return False


def _all_existing_terms(config: dict) -> set[str]:
    """Get all existing keywords, synonyms, and exclude terms as lowercase set."""
    terms: set[str] = set()
    for kw in config.get("keywords", []):
        terms.add(kw.lower())
    for syn in config.get("synonyms", []):
        terms.add(syn.lower())
    for exc in config.get("exclude", []):
        terms.add(exc.lower())
    return terms


def merge_candidates(
    current_configs: list[dict],
    candidates: list[dict],
    max_synonyms: int = 10,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Merge keyword candidates into existing configs (additions only).

    Rules:
    - Never delete existing keywords/synonyms/exclude
    - Skip candidates already present in any config's keywords/synonyms
    - Person entries (genre="" + Japanese name) only accept strict-match candidates
    - Respect max_synonyms limit per config entry
    - Candidates that don't match any config are collected as new genre suggestions

    Args:
        current_configs: Current NEWS_SEARCH_CONFIGS list (will be deep-copied).
        candidates: List of {"keyword": str, "source": str, ...} dicts.
        max_synonyms: Maximum synonyms per config entry.

    Returns:
        Tuple of (updated_configs, changes_log, new_genre_suggestions).
        changes_log: List of {"genre": str, "keywords": list, "added": str, "to": "synonyms"}.
        new_genre_suggestions: List of unmatched candidates with suggested config templates.
    """
    # Deep copy to avoid mutation
    updated = [
        {k: (list(v) if isinstance(v, list) else v) for k, v in cfg.items()}
        for cfg in current_configs
    ]

    changes: list[dict] = []
    new_genre_suggestions: list[dict] = []

    # Build global set of all existing terms across all configs
    global_terms: set[str] = set()
    for cfg in updated:
        global_terms.update(_all_existing_terms(cfg))

    for candidate in candidates:
        kw = candidate["keyword"]
        kw_lower = kw.lower()

        # Skip if already exists anywhere
        if kw_lower in global_terms:
            continue

        # Find best matching config entry
        best_cfg = _find_best_config(updated, candidate)
        if best_cfg is None:
            # No matching config → new genre suggestion
            new_genre_suggestions.append({
                "keyword": kw,
                "frequency": candidate.get("frequency", 0),
                "source": candidate.get("source", "unknown"),
                "suggested_config": {
                    "genre": "テクノロジー",
                    "keywords": [kw],
                    "synonyms": [],
                    "exclude": [],
                    "youtube": True,
                },
            })
            global_terms.add(kw_lower)
            continue

        # Person entries: strict match only
        if _is_person_entry(best_cfg):
            related = candidate.get("related_to", "")
            cfg_keywords = [k.lower() for k in best_cfg.get("keywords", [])]
            if related.lower() not in cfg_keywords:
                continue

        # Check synonyms limit
        current_synonyms = best_cfg.get("synonyms", [])
        if len(current_synonyms) >= max_synonyms:
            continue

        # Add to synonyms
        best_cfg.setdefault("synonyms", []).append(kw)
        global_terms.add(kw_lower)

        changes.append({
            "genre": best_cfg.get("genre", ""),
            "keywords": best_cfg.get("keywords", []),
            "added": kw,
            "to": "synonyms",
            "source": candidate.get("source", "unknown"),
        })

    logger.info("Merged %d new synonyms into configs", len(changes))
    if new_genre_suggestions:
        logger.info("%d candidates suggested as new genres", len(new_genre_suggestions))
    return updated, changes, new_genre_suggestions


def _find_best_config(configs: list[dict], candidate: dict) -> dict | None:
    """Find the best config entry for a candidate keyword.

    Matching strategy:
    1. If candidate has "related_to", find config containing that keyword.
    2. Candidate keyword partially matches a config's keywords/synonyms.
       e.g. "Claude" partially matches "Claude Code" config.
    3. No fallback — returns None if no match (candidate becomes new genre suggestion).
    """
    related_to = candidate.get("related_to", "")
    kw = candidate["keyword"]
    kw_lower = kw.lower()

    # 1. Match by related_to keyword
    if related_to:
        related_lower = related_to.lower()
        for cfg in configs:
            all_kw = [k.lower() for k in cfg.get("keywords", [])]
            all_syn = [s.lower() for s in cfg.get("synonyms", [])]
            if related_lower in all_kw or related_lower in all_syn:
                return cfg

    # 2. Partial match: candidate keyword is a substring of config keywords/synonyms
    #    or a config keyword/synonym is a substring of the candidate
    for cfg in configs:
        if _is_person_entry(cfg):
            continue
        for term in cfg.get("keywords", []) + cfg.get("synonyms", []):
            term_lower = term.lower()
            if kw_lower in term_lower or term_lower in kw_lower:
                return cfg

    # 3. No fallback — return None (candidate will be treated as new genre suggestion)
    return None
