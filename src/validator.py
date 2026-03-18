"""Output JSON validation."""

from __future__ import annotations

import re
from datetime import datetime

VALID_CATEGORIES = {"AI", "DX", "データ", "テクノロジー"}
VALID_TYPES = {"article", "youtube"}

REQUIRED_FIELDS = ["id", "date", "category", "title", "link"]


def validate_news_items(items: list[dict]) -> list[dict]:
    """Validate and clean news items for output.

    Raises:
        ValueError: If items is empty or has invalid structure
    """
    if not items:
        raise ValueError("News items list is empty")

    validated: list[dict] = []
    for i, item in enumerate(items, start=1):
        try:
            validated.append(_validate_item(item, i))
        except ValueError as e:
            # Skip invalid items but log the error
            import logging

            logging.getLogger(__name__).warning("Skipping item %d: %s", i, e)

    if not validated:
        raise ValueError("No valid items after validation")

    return validated


def _validate_item(item: dict, index: int) -> dict:
    """Validate a single news item."""
    if not isinstance(item, dict):
        raise ValueError(f"Item {index} is not a dict")

    title = str(item.get("title", "")).strip()
    if not title:
        raise ValueError(f"Item {index} has empty title")

    link = str(item.get("link", "")).strip()
    if not link or not link.startswith("http"):
        raise ValueError(f"Item {index} has invalid link: {link}")

    date_str = str(item.get("date", "")).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        date_str = datetime.now().strftime("%Y-%m-%d")

    category = str(item.get("category", "テクノロジー")).strip()
    if category not in VALID_CATEGORIES:
        category = "テクノロジー"

    content_type = str(item.get("type", "article")).strip()
    if content_type not in VALID_TYPES:
        content_type = "article"

    return {
        "id": index,
        "date": date_str,
        "category": category,
        "title": title[:100],
        "link": link,
        "source": str(item.get("source", "")).strip()[:50],
        "type": content_type,
        "auto_generated": True,
    }
