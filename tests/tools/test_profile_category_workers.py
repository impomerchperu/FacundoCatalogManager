import pytest

from config.scraping_config import SCRAPING_CATEGORY_WORKERS
from tools.profile_category_workers import _ExperimentScrapingConfig


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
