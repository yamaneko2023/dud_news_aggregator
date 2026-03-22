"""Tests for query builder."""

from src.query_builder import SearchQuery, build_queries, build_queries_from_genres


class TestBuildQueries:
    def test_basic_web_queries(self):
        configs = [
            {
                "genre": "テクノロジー",
                "keywords": ["AI"],
                "synonyms": [],
                "exclude": [],
                "youtube": False,
            },
        ]
        queries = build_queries(configs)
        assert len(queries) == 1
        assert queries[0].query == "テクノロジー AI"
        assert queries[0].genre_label == "AI"
        assert queries[0].source_type == "web"

    def test_synonyms_expand_to_web_queries(self):
        configs = [
            {
                "genre": "テクノロジー",
                "keywords": ["AI"],
                "synonyms": ["生成AI", "機械学習"],
                "exclude": [],
                "youtube": False,
            },
        ]
        queries = build_queries(configs)
        # keyword(1) + synonyms(2) = 3 web queries
        assert len(queries) == 3
        assert queries[0].query == "テクノロジー AI"
        assert queries[1].query == "テクノロジー 生成AI"
        assert queries[2].query == "テクノロジー 機械学習"
        # All should have the first keyword as genre_label
        assert all(q.genre_label == "AI" for q in queries)

    def test_exclude_words_appended(self):
        configs = [
            {
                "genre": "テクノロジー",
                "keywords": ["AI"],
                "synonyms": [],
                "exclude": ["ラブライブ", "アイドル"],
                "youtube": False,
            },
        ]
        queries = build_queries(configs)
        assert queries[0].query == "テクノロジー AI -ラブライブ -アイドル"

    def test_youtube_queries_generated(self):
        configs = [
            {
                "genre": "テクノロジー",
                "keywords": ["AI", "人工知能"],
                "synonyms": ["生成AI"],
                "exclude": ["ラブライブ"],
                "youtube": True,
            },
        ]
        queries = build_queries(configs)
        web_queries = [q for q in queries if q.source_type == "web"]
        yt_queries = [q for q in queries if q.source_type == "youtube"]

        # web: keywords(2) + synonyms(1) = 3
        assert len(web_queries) == 3
        # youtube: keywords only(2)
        assert len(yt_queries) == 2
        assert yt_queries[0].query == "テクノロジー AI -ラブライブ"
        assert yt_queries[1].query == "テクノロジー 人工知能 -ラブライブ"

    def test_empty_genre(self):
        configs = [
            {
                "genre": "",
                "keywords": ["今井翔太"],
                "synonyms": [],
                "exclude": [],
                "youtube": True,
            },
        ]
        queries = build_queries(configs)
        assert queries[0].query == "今井翔太"
        assert queries[0].genre_label == "今井翔太"

    def test_multiple_configs(self):
        configs = [
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
        queries = build_queries(configs)
        # Config 1: 1 web + 1 yt = 2
        # Config 2: 1 web + 1 yt = 2
        assert len(queries) == 4

    def test_all_keywords_get_youtube(self):
        """All keywords should have youtube=True by default."""
        configs = [
            {
                "genre": "テクノロジー",
                "keywords": ["AI"],
                "synonyms": ["生成AI"],
                "exclude": [],
                "youtube": True,
            },
            {
                "genre": "テクノロジー",
                "keywords": ["Claude Code"],
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
        queries = build_queries(configs)
        yt_queries = [q for q in queries if q.source_type == "youtube"]
        # Each config has youtube=True, so each keyword gets a yt query
        assert len(yt_queries) == 3


class TestBuildQueriesFromGenres:
    def test_legacy_fallback(self):
        queries = build_queries_from_genres("AI,Claude Code,今井翔太")
        assert len(queries) == 6  # 3 genres * (web + youtube)
        web = [q for q in queries if q.source_type == "web"]
        yt = [q for q in queries if q.source_type == "youtube"]
        assert len(web) == 3
        assert len(yt) == 3
        assert web[0].query == "AI"
        assert web[0].genre_label == "AI"

    def test_empty_string(self):
        queries = build_queries_from_genres("")
        assert queries == []
