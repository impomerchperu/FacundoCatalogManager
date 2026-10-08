from services.scraping.scraping_runner import ScrapingRunner


def test_progress_contract_reports_collection_then_terminal_pipeline_completion():
    progress = []

    class FakeScrapingService:
        def sync_categories(self, categories, progress_callback=None):
            assert progress_callback is not None
            for current in range(1, len(categories) + 1):
                progress_callback(current, len(categories))
            return []

    runner = ScrapingRunner(FakeScrapingService())

    runner.run(
        ["cat1", "cat2", "cat3"],
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert progress == [(1, 9), (2, 9), (3, 9), (9, 9)]


def test_progress_contract_does_not_expose_unvalidated_enrichment_steps():
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

    assert progress == [(1, 6), (2, 6), (6, 6)]
    assert all(current not in {3} for current, _ in progress)
