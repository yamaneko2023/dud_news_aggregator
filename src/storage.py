"""Atomic JSON storage with backup."""

import json
import logging
import os
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)


class NewsStorage:
    """Save news JSON with atomic writes and backup."""

    def __init__(self, data_dir: str, filename: str = "tech_news.json"):
        self.data_dir = data_dir
        self.target_file = os.path.join(data_dir, filename)

    def save(self, items: list[dict], max_items: int = 10) -> str:
        """Save news items with wrapper format. Returns the saved file path."""
        os.makedirs(self.data_dir, exist_ok=True)

        items = items[:max_items]
        wrapper = {
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(items),
            "items": items,
        }

        json_str = json.dumps(wrapper, ensure_ascii=False, indent=2)

        # Atomic write via temp file + rename
        tmp_file = self.target_file + ".tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(json_str + "\n")
            os.replace(tmp_file, self.target_file)
        except Exception:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            raise

        logger.info("Saved %d items to %s", len(items), self.target_file)
        return self.target_file

    def backup(self) -> str | None:
        """Backup existing file with timestamp. Returns backup path or None."""
        if not os.path.exists(self.target_file):
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_file = os.path.join(
            self.data_dir, f"tech_news_{timestamp}.json"
        )
        shutil.copy2(self.target_file, backup_file)
        logger.info("Backup: %s", backup_file)
        return backup_file

    def load_existing(self) -> list[dict] | None:
        """Load existing news items. Returns None if file doesn't exist."""
        if not os.path.exists(self.target_file):
            return None

        try:
            with open(self.target_file, encoding="utf-8") as f:
                data = json.load(f)

            # Support both wrapper and raw list format
            if isinstance(data, dict) and "items" in data:
                return data["items"]
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load existing file: %s", self.target_file)

        return None
