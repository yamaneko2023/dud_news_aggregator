"""Tests for src/storage.py archive_previous_months()."""

import os
import tarfile
from datetime import datetime
from unittest.mock import patch

import pytest

from src.storage import NewsStorage


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)


def _create_backup(data_dir: str, name: str, content: str = "{}") -> str:
    path = os.path.join(data_dir, name)
    with open(path, "w") as f:
        f.write(content)
    return path


class TestArchivePreviousMonths:
    def test_archives_previous_month(self, tmp_data_dir):
        """前月バックアップが tar.gz にアーカイブされる。"""
        _create_backup(tmp_data_dir, "tech_news_2026-02-15_090000.json")
        _create_backup(tmp_data_dir, "tech_news_2026-02-20_180000.json")

        with patch("src.storage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 18, 10, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            storage = NewsStorage(data_dir=tmp_data_dir)
            archives = storage.archive_previous_months()

        assert len(archives) == 1
        archive_path = archives[0]
        assert archive_path.endswith("2026-02.tar.gz")
        assert os.path.exists(archive_path)

        # Original files should be removed
        assert not os.path.exists(
            os.path.join(tmp_data_dir, "tech_news_2026-02-15_090000.json")
        )
        assert not os.path.exists(
            os.path.join(tmp_data_dir, "tech_news_2026-02-20_180000.json")
        )

        # Verify archive contents
        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
        assert "tech_news_2026-02-15_090000.json" in names
        assert "tech_news_2026-02-20_180000.json" in names

        # Month directory should be cleaned up
        assert not os.path.isdir(os.path.join(tmp_data_dir, "2026-02"))

    def test_current_month_not_archived(self, tmp_data_dir):
        """今月分のバックアップは移動されない。"""
        _create_backup(tmp_data_dir, "tech_news_2026-03-17_090000.json")
        _create_backup(tmp_data_dir, "tech_news_2026-03-18_090000.json")

        with patch("src.storage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 18, 10, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            storage = NewsStorage(data_dir=tmp_data_dir)
            archives = storage.archive_previous_months()

        assert archives == []
        # Files should still be in place
        assert os.path.exists(
            os.path.join(tmp_data_dir, "tech_news_2026-03-17_090000.json")
        )
        assert os.path.exists(
            os.path.join(tmp_data_dir, "tech_news_2026-03-18_090000.json")
        )

    def test_multiple_months(self, tmp_data_dir):
        """複数月分がそれぞれアーカイブされる。"""
        _create_backup(tmp_data_dir, "tech_news_2026-01-10_090000.json")
        _create_backup(tmp_data_dir, "tech_news_2026-02-15_090000.json")

        with patch("src.storage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 18, 10, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            storage = NewsStorage(data_dir=tmp_data_dir)
            archives = storage.archive_previous_months()

        assert len(archives) == 2
        basenames = [os.path.basename(a) for a in archives]
        assert "2026-01.tar.gz" in basenames
        assert "2026-02.tar.gz" in basenames

    def test_empty_data_dir(self, tmp_data_dir):
        """空の data/ ディレクトリでエラーにならない。"""
        storage = NewsStorage(data_dir=tmp_data_dir)
        archives = storage.archive_previous_months()
        assert archives == []

    def test_nonexistent_data_dir(self, tmp_path):
        """存在しない data/ ディレクトリでエラーにならない。"""
        storage = NewsStorage(data_dir=str(tmp_path / "nonexistent"))
        archives = storage.archive_previous_months()
        assert archives == []

    def test_tech_news_json_not_archived(self, tmp_data_dir):
        """tech_news.json 本体は対象外。"""
        _create_backup(tmp_data_dir, "tech_news.json")
        _create_backup(tmp_data_dir, "tech_news_2026-02-15_090000.json")

        with patch("src.storage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 18, 10, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            storage = NewsStorage(data_dir=tmp_data_dir)
            storage.archive_previous_months()

        # tech_news.json should remain untouched
        assert os.path.exists(os.path.join(tmp_data_dir, "tech_news.json"))

    def test_skip_existing_archive(self, tmp_data_dir):
        """既にアーカイブ済み（.tar.gz 存在）の月はスキップする。"""
        _create_backup(tmp_data_dir, "tech_news_2026-02-15_090000.json")

        # Pre-create an archive
        existing_archive = os.path.join(tmp_data_dir, "2026-02.tar.gz")
        with open(existing_archive, "w") as f:
            f.write("dummy")

        with patch("src.storage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 18, 10, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            storage = NewsStorage(data_dir=tmp_data_dir)
            archives = storage.archive_previous_months()

        # Should skip, not create a new one
        assert archives == []
        # Original file should still be there (not moved)
        assert os.path.exists(
            os.path.join(tmp_data_dir, "tech_news_2026-02-15_090000.json")
        )
        # Existing archive should be untouched
        with open(existing_archive) as f:
            assert f.read() == "dummy"
