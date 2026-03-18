"""Config file backup and atomic write for NEWS_SEARCH_CONFIGS."""

import importlib
import json
import logging
import os
import shutil
import sys
import types
from datetime import datetime

logger = logging.getLogger(__name__)


def load_config_module(config_path: str) -> types.ModuleType:
    """Load config.py as a module using importlib.

    Args:
        config_path: Absolute path to config.py.

    Returns:
        Loaded module object.
    """
    spec = importlib.util.spec_from_file_location("_config_tmp", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load config from {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def backup_config(config_path: str) -> str:
    """Create a timestamped backup of config.py.

    Returns:
        Path to the backup file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{config_path}.bak.{timestamp}"
    shutil.copy2(config_path, backup_path)
    logger.info("Backup created: %s", backup_path)
    return backup_path


def _format_config_value(value, indent_level: int = 0) -> str:
    """Format a Python value as a string for config file output."""
    indent = "    " * indent_level

    if isinstance(value, str):
        # Use double quotes, escape internal quotes
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    elif isinstance(value, bool):
        return "True" if value else "False"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, list):
        if not value:
            return "[]"
        # Check if it's a list of dicts (like NEWS_SEARCH_CONFIGS)
        if isinstance(value[0], dict):
            items = []
            for item in value:
                items.append(_format_dict(item, indent_level + 1))
            inner = ",\n".join(items)
            return f"[\n{inner},\n{indent}]"
        else:
            # Simple list (strings, numbers)
            items = [_format_config_value(v) for v in value]
            joined = ", ".join(items)
            if len(joined) > 60:
                inner_indent = indent + "    "
                formatted_items = [f"{inner_indent}{item}" for item in items]
                return "[\n" + ",\n".join(formatted_items) + f",\n{indent}]"
            return f"[{joined}]"
    elif isinstance(value, dict):
        return _format_dict(value, indent_level)
    else:
        return repr(value)


def _format_dict(d: dict, indent_level: int = 0) -> str:
    """Format a dict for config file output."""
    indent = "    " * indent_level
    inner_indent = "    " * (indent_level + 1)

    items = []
    for k, v in d.items():
        formatted_v = _format_config_value(v, indent_level + 1)
        items.append(f'{inner_indent}"{k}": {formatted_v}')

    return indent + "{\n" + ",\n".join(items) + ",\n" + indent + "}"


def generate_config_content(
    original_content: str,
    updated_configs: list[dict],
) -> str:
    """Generate new config.py content with updated NEWS_SEARCH_CONFIGS.

    Preserves all other variables and comments. Only replaces the
    NEWS_SEARCH_CONFIGS assignment block.

    Args:
        original_content: Original config.py file content.
        updated_configs: New NEWS_SEARCH_CONFIGS value.

    Returns:
        New config.py content string.
    """
    lines = original_content.split("\n")
    result_lines: list[str] = []

    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]

        # Detect NEWS_SEARCH_CONFIGS assignment
        stripped = line.lstrip()
        if stripped.startswith("NEWS_SEARCH_CONFIGS") and "=" in stripped and not replaced:
            # Generate new assignment
            formatted = _format_config_value(updated_configs)
            result_lines.append(f"NEWS_SEARCH_CONFIGS = {formatted}")
            replaced = True

            # Skip original lines until the assignment ends
            # Track bracket depth to find the end
            bracket_depth = 0
            started = False
            while i < len(lines):
                for ch in lines[i]:
                    if ch == "[":
                        bracket_depth += 1
                        started = True
                    elif ch == "]":
                        bracket_depth -= 1
                if started and bracket_depth <= 0:
                    break
                i += 1
            i += 1
            continue

        result_lines.append(line)
        i += 1

    if not replaced:
        # NEWS_SEARCH_CONFIGS not found in original, append it
        formatted = _format_config_value(updated_configs)
        result_lines.append("")
        result_lines.append(f"NEWS_SEARCH_CONFIGS = {formatted}")

    return "\n".join(result_lines)


def write_config(config_path: str, content: str) -> None:
    """Write config.py atomically (tmp + os.replace).

    Also performs syntax check with compile() before replacing.
    Rolls back on syntax error.

    Args:
        config_path: Path to config.py.
        content: New file content.

    Raises:
        SyntaxError: If generated content has syntax errors.
    """
    # Syntax check before writing
    try:
        compile(content, config_path, "exec")
    except SyntaxError as e:
        logger.error("Generated config has syntax error: %s", e)
        raise

    tmp_path = config_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, config_path)
        logger.info("Config updated: %s", config_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def save_suggestions(
    output_path: str,
    candidates: list[dict],
    changes: list[dict],
    new_genre_suggestions: list[dict] | None = None,
) -> str:
    """Save keyword suggestions to JSON file (dry-run output).

    Args:
        output_path: Path to write suggestions JSON.
        candidates: Raw keyword candidates.
        changes: Merge changes log.
        new_genre_suggestions: Unmatched candidates suggested as new genres.

    Returns:
        Path to the saved file.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "candidates": candidates,
        "changes": changes,
        "new_genre_suggestions": new_genre_suggestions or [],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    logger.info("Suggestions saved: %s", output_path)
    return output_path
