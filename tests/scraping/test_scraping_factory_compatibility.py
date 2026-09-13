from typing import ClassVar

from factories.scraping_factory import (
    ScrapingFactory as ApplicationScrapingFactory,
)
from scrapers.factories.scraping_factory import (
    ScrapingFactory as ScraperScrapingFactory,
)


class FakeCanonicalFactory:
    calls: ClassVar[list[object | None]] = []

    @staticmethod
    def create_runner(config=None):
        FakeCanonicalFactory.calls.append(config)
        return "canonical-runner"


def test_application_factory_delegates_to_canonical(monkeypatch):
    monkeypatch.setattr(
        "factories.scraping_factory.CanonicalScrapingFactory",
        FakeCanonicalFactory,
    )
    config = object()

    assert ApplicationScrapingFactory.create_runner(config) == "canonical-runner"
    assert FakeCanonicalFactory.calls == [config]


def test_scraper_factory_preserves_create_api(monkeypatch):
    monkeypatch.setattr(
        "scrapers.factories.scraping_factory.CanonicalScrapingFactory",
        FakeCanonicalFactory,
    )
    FakeCanonicalFactory.calls.clear()

    assert ScraperScrapingFactory.create() == "canonical-runner"
    assert FakeCanonicalFactory.calls == [None]
