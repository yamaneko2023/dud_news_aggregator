"""Tests for merger module."""

import pytest

from src.keyword_optimizer.merger import merge_candidates


SAMPLE_CONFIGS = [
    {
        "genre": "テクノロジー",
        "keywords": ["AI", "人工知能"],
        "synonyms": ["生成AI", "機械学習", "LLM"],
        "exclude": ["ラブライブ"],
        "youtube": True,
    },
    {
        "genre": "テクノロジー",
        "keywords": ["Claude Code"],
        "synonyms": ["Anthropic Claude"],
        "exclude": [],
        "youtube": True,
    },
    {
        "genre": "",
        "keywords": ["今井翔太"],
        "synonyms": ["今井翔太 AI"],
        "exclude": [],
        "youtube": True,
    },
]


class TestMergeCandidates:
    def test_add_new_synonym_via_partial_match(self):
        candidates = [
            {"keyword": "AIエージェント", "source": "hatena", "frequency": 5},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        # "AIエージェント" contains "AI" → matches first config
        first_synonyms = updated[0]["synonyms"]
        assert "AIエージェント" in first_synonyms
        assert len(changes) == 1
        assert changes[0]["added"] == "AIエージェント"

    def test_skip_existing_keyword(self):
        candidates = [
            {"keyword": "AI", "source": "hatena", "frequency": 10},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        assert len(changes) == 0

    def test_skip_existing_synonym(self):
        candidates = [
            {"keyword": "LLM", "source": "hatena", "frequency": 5},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        assert len(changes) == 0

    def test_case_insensitive_dedup(self):
        candidates = [
            {"keyword": "llm", "source": "hatena", "frequency": 5},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        assert len(changes) == 0

    def test_person_entry_strict_match(self):
        # "GPT-5" should NOT be added to person entry "今井翔太"
        candidates = [
            {"keyword": "GPT-5", "source": "hatena", "frequency": 3},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        person_synonyms = updated[2]["synonyms"]
        assert "GPT-5" not in person_synonyms

    def test_person_entry_related_match(self):
        # keyword related to "今井翔太" CAN be added to person entry
        candidates = [
            {"keyword": "東大教授", "source": "cooccurrence",
             "related_to": "今井翔太", "cooccurrence_score": 3.0},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        person_synonyms = updated[2]["synonyms"]
        assert "東大教授" in person_synonyms

    def test_max_synonyms_limit(self):
        candidates = [
            {"keyword": f"AITerm{i}", "source": "hatena", "frequency": 5}
            for i in range(20)
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates, max_synonyms=5)
        # First config starts with 3 synonyms, can add 2 more
        first_synonyms = updated[0]["synonyms"]
        assert len(first_synonyms) <= 5

    def test_no_mutation_of_original(self):
        original_synonyms = list(SAMPLE_CONFIGS[0]["synonyms"])
        candidates = [
            {"keyword": "AINewTerm", "source": "hatena", "frequency": 5},
        ]
        merge_candidates(SAMPLE_CONFIGS, candidates)
        assert SAMPLE_CONFIGS[0]["synonyms"] == original_synonyms

    def test_related_to_routing(self):
        candidates = [
            {"keyword": "Claude 4", "source": "cooccurrence",
             "related_to": "Claude Code", "cooccurrence_score": 5.0},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        # Should be added to Claude Code config, not AI config
        claude_synonyms = updated[1]["synonyms"]
        assert "Claude 4" in claude_synonyms

    def test_skip_exclude_terms(self):
        candidates = [
            {"keyword": "ラブライブ", "source": "hatena", "frequency": 10},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        assert len(changes) == 0

    def test_empty_candidates(self):
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, [])
        assert changes == []
        assert new_genres == []
        assert len(updated) == len(SAMPLE_CONFIGS)

    def test_changes_log_format(self):
        candidates = [
            {"keyword": "AITransformer", "source": "hatena", "frequency": 3},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        assert len(changes) == 1
        change = changes[0]
        assert "genre" in change
        assert "keywords" in change
        assert "added" in change
        assert "to" in change
        assert "source" in change


class TestPartialMatchRouting:
    """Test that partial keyword matching routes candidates correctly."""

    def test_claude_routes_to_claude_code_config(self):
        """'Claude' should match 'Claude Code' config via partial match."""
        candidates = [
            {"keyword": "Claude", "source": "hatena", "frequency": 5},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        claude_synonyms = updated[1]["synonyms"]
        assert "Claude" in claude_synonyms
        # Should NOT be in AI config
        ai_synonyms = updated[0]["synonyms"]
        assert "Claude" not in ai_synonyms

    def test_anthropic_routes_to_claude_code_config(self):
        """'Anthropic' should match 'Anthropic Claude' synonym via partial match."""
        candidates = [
            {"keyword": "Anthropic", "source": "hatena", "frequency": 3},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        claude_synonyms = updated[1]["synonyms"]
        assert "Anthropic" in claude_synonyms


class TestNewGenreSuggestions:
    """Test that unmatched candidates become new genre suggestions."""

    def test_unmatched_becomes_new_genre(self):
        """Candidate that doesn't match any config → new genre suggestion."""
        candidates = [
            {"keyword": "Rust", "source": "hatena", "frequency": 5},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        assert len(changes) == 0
        assert len(new_genres) == 1
        assert new_genres[0]["keyword"] == "Rust"
        assert new_genres[0]["frequency"] == 5
        assert new_genres[0]["source"] == "hatena"
        assert new_genres[0]["suggested_config"]["keywords"] == ["Rust"]

    def test_multiple_unmatched(self):
        """Multiple unmatched candidates each get their own suggestion."""
        candidates = [
            {"keyword": "Rust", "source": "hatena", "frequency": 5},
            {"keyword": "Kubernetes", "source": "hatena", "frequency": 3},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        assert len(new_genres) == 2
        keywords = [s["keyword"] for s in new_genres]
        assert "Rust" in keywords
        assert "Kubernetes" in keywords

    def test_no_fallback_to_first_config(self):
        """Unmatched candidates must NOT fall back to first non-person config."""
        candidates = [
            {"keyword": "Terraform", "source": "hatena", "frequency": 4},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        # Should NOT be added to any existing config
        for cfg in updated:
            assert "Terraform" not in cfg.get("synonyms", [])
        # Should be in new genre suggestions
        assert len(new_genres) == 1

    def test_suggested_config_format(self):
        """New genre suggestion should have a valid config template."""
        candidates = [
            {"keyword": "Docker", "source": "hatena", "frequency": 3},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        suggestion = new_genres[0]
        cfg = suggestion["suggested_config"]
        assert cfg["genre"] == "テクノロジー"
        assert cfg["keywords"] == ["Docker"]
        assert cfg["synonyms"] == []
        assert cfg["exclude"] == []
        assert cfg["youtube"] is True

    def test_duplicate_unmatched_not_repeated(self):
        """Same keyword appearing twice should only generate one suggestion."""
        candidates = [
            {"keyword": "Rust", "source": "hatena", "frequency": 5},
            {"keyword": "Rust", "source": "cooccurrence", "frequency": 3},
        ]
        updated, changes, new_genres = merge_candidates(SAMPLE_CONFIGS, candidates)
        # Second "Rust" should be skipped (already in global_terms)
        assert len(new_genres) == 1
