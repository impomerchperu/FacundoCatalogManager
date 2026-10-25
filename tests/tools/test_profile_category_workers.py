import sqlite3

import pytest

from config import runtime_paths
from config.scraping_config import SCRAPING_CATEGORY_WORKERS
from database import db_manager
from services.scraping import scraping_factory
from tools.profile_category_workers import (
    _ExperimentScrapingConfig,
    _configure_isolated_database,
)


def test_experiment_config_defaults_to_production_workers(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_CATEGORY_WORKERS", raising=False)

    config = _ExperimentScrapingConfig()

    assert config.category_workers == SCRAPING_CATEGORY_WORKERS


def test_experiment_config_accepts_positive_override(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_CATEGORY_WORKERS", "24")

    config = _ExperimentScrapingConfig()

    assert config.category_workers == 24


@pytest.mark.parametrize("value", ["0", "-1"])
def test_experiment_config_rejects_non_positive_override(monkeypatch, value):
    monkeypatch.setenv("FCM_PROFILE_CATEGORY_WORKERS", value)

    with pytest.raises(ValueError, match="FCM_PROFILE_CATEGORY_WORKERS"):
        _ExperimentScrapingConfig()


def _make_test_catalog(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE products (code TEXT)")
        connection.execute("CREATE TABLE schema_migrations (version INTEGER)")
        connection.execute("INSERT INTO schema_migrations(version) VALUES (6)")


def test_profile_requires_an_explicit_isolated_database(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_DB_PATH", raising=False)

    with pytest.raises(ValueError, match="FCM_PROFILE_DB_PATH es obligatorio"):
        _configure_isolated_database()


def test_profile_refuses_the_canonical_project_database(monkeypatch, tmp_path):
    canonical = tmp_path / "catalog.db"
    _make_test_catalog(canonical)
    monkeypatch.setattr(runtime_paths, "DATABASE_PATH", canonical)
    monkeypatch.setenv("FCM_PROFILE_DB_PATH", str(canonical))

    with pytest.raises(ValueError, match="base canónica"):
        _configure_isolated_database()


def test_profile_accepts_verified_isolated_database_and_redirects_dependencies(
    monkeypatch, tmp_path
):
    canonical = tmp_path / "project" / "catalog.db"
    canonical.parent.mkdir()
    _make_test_catalog(canonical)
    isolated = tmp_path / "temp" / "profile.db"
    isolated.parent.mkdir()
    _make_test_catalog(isolated)

    monkeypatch.setattr(runtime_paths, "DATABASE_PATH", canonical)
    monkeypatch.setattr(db_manager, "DATABASE_PATH", canonical)
    monkeypatch.setattr(scraping_factory, "DATABASE_PATH", canonical)
    monkeypatch.setenv("FCM_PROFILE_DB_PATH", str(isolated))

    assert _configure_isolated_database() == isolated.resolve()
    assert db_manager.DATABASE_PATH == isolated.resolve()
    assert scraping_factory.DATABASE_PATH == isolated.resolve()
