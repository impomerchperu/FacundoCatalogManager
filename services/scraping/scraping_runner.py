class ScrapingRunner:
    def __init__(self, scraping_service):

        self.scraping_service = scraping_service

    def run(self, categories, progress_callback=None):

        results = []

        total = len(categories)

        for index, category in enumerate(categories, start=1):
            products = self.scraping_service.scrape_category(category)

            results.extend(products)

            if progress_callback:
                progress_callback(index, total)

        return results
