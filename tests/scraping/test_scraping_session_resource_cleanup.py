from types import SimpleNamespace

from services.scraping.scraping_session import ScrapingSession


class RecordingExecutor:
    def __init__(self):
        self.calls = []

    def shutdown(self, *, wait, cancel_futures):
        self.calls.append((wait, cancel_futures))


def test_scraping_session_closes_detail_executors_after_error():
    detail_executor = RecordingExecutor()
    fetch_executor = RecordingExecutor()
    scraper = SimpleNamespace(
        _detail_executor=detail_executor,
        _detail_fetch_executor=fetch_executor,
    )
    scraping_service = SimpleNamespace(scraper=scraper)
    sync_service = SimpleNamespace(scraper_service=scraping_service)
    runner = SimpleNamespace(scraping_service=sync_service)

    session = ScrapingSession(runner)
    result = session._execute(
        lambda: (_ for _ in ()).throw(RuntimeError("scraping failed"))
    )

    assert result.errors == ["scraping failed"]
    assert detail_executor.calls == [(True, True)]
    assert fetch_executor.calls == [(True, True)]


def test_scraping_session_does_not_shutdown_duplicate_executor_twice():
    executor = RecordingExecutor()
    scraper = SimpleNamespace(
        _detail_executor=executor,
        _detail_fetch_executor=executor,
    )
    scraping_service = SimpleNamespace(scraper=scraper)
    sync_service = SimpleNamespace(scraper_service=scraping_service)
    runner = SimpleNamespace(scraping_service=sync_service)

    session = ScrapingSession(runner)
    session._close_scraping_resources()

    assert executor.calls == [(True, True)]
