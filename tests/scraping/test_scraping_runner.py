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
