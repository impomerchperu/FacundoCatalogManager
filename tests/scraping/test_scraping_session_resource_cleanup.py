from types import SimpleNamespace

from services.scraping.scraping_session import ScrapingSession


class RecordingScraperService:
    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


def test_scraping_session_does_not_close_resources_after_execution():
    scraper_service = RecordingScraperService()
    sync_service = SimpleNamespace(scraper_service=scraper_service)
    runner = SimpleNamespace(scraping_service=sync_service)

    session = ScrapingSession(runner)
    result = session._execute(lambda: [])

    assert result.errors == []
    assert scraper_service.close_calls == 0


def test_scraping_session_closes_resources_explicitly():
    scraper_service = RecordingScraperService()
    sync_service = SimpleNamespace(scraper_service=scraper_service)
    runner = SimpleNamespace(scraping_service=sync_service)

    session = ScrapingSession(runner)
    session.close()
    session.close()

    assert scraper_service.close_calls == 2


def test_scraping_session_close_is_tolerant_of_missing_close_api():
    sync_service = SimpleNamespace(scraper_service=SimpleNamespace())
    runner = SimpleNamespace(scraping_service=sync_service)

    session = ScrapingSession(runner)
    session.close()
