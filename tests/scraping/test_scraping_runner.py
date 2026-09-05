from pathlib import Path

import pytest

from services.scraping import scraping_runner
from services.scraping.scraping_runner import ScrapingRunner


def test_scraping_runner_executes_categories():
    class FakeScrapingService:
        def scrape_category(self, category):
            return [category]

    progress = []

    def callback(current, total):
        progress.append((current, total))

    runner = ScrapingRunner(FakeScrapingService())

    result = runner.run(["cat1", "cat2"], progress_callback=callback)

    assert result == ["cat1", "cat2"]
    assert progress == [(1, 2), (2, 2)]


def test_scraping_runner_marks_directed_mode():
    class FakeScrapingService:
        def sync_categories(self, categories, progress_callback=None):
            return []

    service = FakeScrapingService()
    runner = ScrapingRunner(service)

    runner.run(["cat1"])

    assert service._scraping_mode == "directed"


def test_scraping_runner_marks_full_mode_for_run_all():
    class FakeScrapingService:
        def sync_categories(self, categories, progress_callback=None):
            return []

    class FakeCategoryService:
        def scrape_all(self):
            return ["cat1", "cat2"]

    service = FakeScrapingService()
    runner = ScrapingRunner(service, category_service=FakeCategoryService())

    runner.run_all()

    assert service._scraping_mode == "full"


def test_scraping_runner_scales_sync_categories_progress_to_full_pipeline():
    progress = []

    class FakeScrapingService:
        def sync_categories(self, categories, progress_callback=None):
            assert progress_callback is not None
            progress_callback(1, len(categories))
            progress_callback(2, len(categories))
            return []

    runner = ScrapingRunner(FakeScrapingService())

    runner.run(
        ["cat1", "cat2"],
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert progress == [(1, 4), (2, 4), (4, 4)]


def test_scraping_runner_logs_error_and_total_on_sync_failure(tmp_path, monkeypatch):
    timing_log = tmp_path / "scraping_timing.log"
    monkeypatch.setattr(scraping_runner, "TIMING_LOG", Path(timing_log))

    class FakeScrapingService:
        def sync_categories(self, categories, progress_callback=None):
            raise RuntimeError(f"fallo en {categories[0].url}")

    class Category:
        url = "https://example.test/categoria"

    runner = ScrapingRunner(FakeScrapingService())

    with pytest.raises(RuntimeError, match="fallo en"):
        runner.run([Category()])

    content = timing_log.read_text(encoding="utf-8")
    assert "stage=run_error" in content
    assert "error_type=RuntimeError" in content
    assert "fallo en https://example.test/categoria" in content
    assert "stage=run_traceback" in content
    assert "stage=run_total | categories=1" in content
