from services.scraping.scraping_runner import ScrapingRunner
from services.scraping.scraping_session import ScrapingSession


class RecordingResource:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class RecordingScrapingService:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def test_scraping_runner_closes_pipeline_and_owned_resources_once() -> None:
    scraping_service = RecordingScrapingService()
    resource = RecordingResource()
    runner = ScrapingRunner(
        scraping_service,
        owned_resources=(resource, resource),
    )

    runner.close()
    runner.close()

    assert scraping_service.close_calls == 1
    assert resource.close_calls == 1


def test_scraping_session_delegates_close_to_runner() -> None:
    runner = RecordingResource()
    session = ScrapingSession(runner)

    session.close()
    session.close()

    assert runner.close_calls == 2


class RecordingScraperService:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def test_scraping_runner_reaches_nested_scraper_service_close() -> None:
    nested = RecordingScraperService()

    class SyncService:
        scraper_service = nested

    runner = ScrapingRunner(SyncService())

    runner.close()

    assert nested.close_calls == 1
