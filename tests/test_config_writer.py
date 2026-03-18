"""Tests for config_writer module."""

import json
import os
import tempfile

import pytest

from src.keyword_optimizer.config_writer import (
    backup_config,
    generate_config_content,
    load_config_module,
    save_suggestions,
    write_config,
)


SAMPLE_CONFIG_CONTENT = '''# Config file
NEWS_MAX_ITEMS = 10
NEWS_DAYS = 7

NEWS_SEARCH_CONFIGS = [
    {
        "genre": "テクノロジー",
        "keywords": ["AI", "人工知能"],
        "synonyms": ["生成AI"],
        "exclude": [],
        "youtube": True,
    },
]

LLM_PROVIDER = "none"
'''

UPDATED_CONFIGS = [
    {
        "genre": "テクノロジー",
        "keywords": ["AI", "人工知能"],
        "synonyms": ["生成AI", "RAG"],
        "exclude": [],
        "youtube": True,
    },
]


class TestLoadConfigModule:
    def test_load_valid_config(self, tmp_path):
        config_path = str(tmp_path / "config.py")
        with open(config_path, "w") as f:
            f.write("NEWS_MAX_ITEMS = 10\nNEWS_DAYS = 7\n")

        module = load_config_module(config_path)
        assert module.NEWS_MAX_ITEMS == 10
        assert module.NEWS_DAYS == 7

    def test_load_with_search_configs(self, tmp_path):
        config_path = str(tmp_path / "config.py")
        with open(config_path, "w") as f:
            f.write(SAMPLE_CONFIG_CONTENT)

        module = load_config_module(config_path)
        assert len(module.NEWS_SEARCH_CONFIGS) == 1
        assert module.NEWS_SEARCH_CONFIGS[0]["genre"] == "テクノロジー"

    def test_load_nonexistent_file(self):
        with pytest.raises((ImportError, FileNotFoundError)):
            load_config_module("/nonexistent/config.py")


class TestBackupConfig:
    def test_creates_backup(self, tmp_path):
        config_path = str(tmp_path / "config.py")
        with open(config_path, "w") as f:
            f.write("TEST = True\n")

        backup_path = backup_config(config_path)
        assert os.path.exists(backup_path)
        assert ".bak." in backup_path

        with open(backup_path) as f:
            assert f.read() == "TEST = True\n"


class TestGenerateConfigContent:
    def test_replaces_search_configs(self):
        result = generate_config_content(SAMPLE_CONFIG_CONTENT, UPDATED_CONFIGS)

        # Should preserve other variables
        assert "NEWS_MAX_ITEMS = 10" in result
        assert "NEWS_DAYS = 7" in result
        assert 'LLM_PROVIDER = "none"' in result

        # Should contain updated configs
        assert '"RAG"' in result
        assert "NEWS_SEARCH_CONFIGS" in result

    def test_preserves_comments(self):
        result = generate_config_content(SAMPLE_CONFIG_CONTENT, UPDATED_CONFIGS)
        assert "# Config file" in result

    def test_syntax_valid(self):
        result = generate_config_content(SAMPLE_CONFIG_CONTENT, UPDATED_CONFIGS)
        # Should be valid Python
        compile(result, "<test>", "exec")

    def test_no_existing_configs(self):
        content = "NEWS_MAX_ITEMS = 10\n"
        result = generate_config_content(content, UPDATED_CONFIGS)
        assert "NEWS_SEARCH_CONFIGS" in result
        assert "NEWS_MAX_ITEMS = 10" in result

    def test_multiline_configs_replacement(self):
        content = '''FOO = 1
NEWS_SEARCH_CONFIGS = [
    {
        "genre": "テクノロジー",
        "keywords": ["AI"],
        "synonyms": [],
        "exclude": [],
        "youtube": True,
    },
    {
        "genre": "",
        "keywords": ["今井翔太"],
        "synonyms": [],
        "exclude": [],
        "youtube": True,
    },
]
BAR = 2
'''
        result = generate_config_content(content, UPDATED_CONFIGS)
        assert "FOO = 1" in result
        assert "BAR = 2" in result
        assert '"RAG"' in result
        compile(result, "<test>", "exec")


class TestWriteConfig:
    def test_atomic_write(self, tmp_path):
        config_path = str(tmp_path / "config.py")
        content = "NEWS_MAX_ITEMS = 10\n"
        write_config(config_path, content)

        with open(config_path) as f:
            assert f.read() == content

    def test_syntax_error_raises(self, tmp_path):
        config_path = str(tmp_path / "config.py")
        with open(config_path, "w") as f:
            f.write("VALID = True\n")

        with pytest.raises(SyntaxError):
            write_config(config_path, "invalid python {{{}}")

    def test_no_tmp_left_on_error(self, tmp_path):
        config_path = str(tmp_path / "config.py")
        with open(config_path, "w") as f:
            f.write("VALID = True\n")

        try:
            write_config(config_path, "invalid {{{}}")
        except SyntaxError:
            pass

        tmp_path_file = config_path + ".tmp"
        assert not os.path.exists(tmp_path_file)


class TestSaveSuggestions:
    def test_saves_json(self, tmp_path):
        output_path = str(tmp_path / "config" / "keyword_suggestions.json")
        candidates = [{"keyword": "RAG", "source": "hatena", "frequency": 5}]
        changes = [{"added": "RAG", "to": "synonyms"}]

        result = save_suggestions(output_path, candidates, changes)
        assert os.path.exists(result)

        with open(result, encoding="utf-8") as f:
            data = json.load(f)
        assert "generated_at" in data
        assert len(data["candidates"]) == 1
        assert len(data["changes"]) == 1

    def test_creates_directory(self, tmp_path):
        output_path = str(tmp_path / "nested" / "dir" / "suggestions.json")
        save_suggestions(output_path, [], [])
        assert os.path.exists(output_path)
