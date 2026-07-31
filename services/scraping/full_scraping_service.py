class FullScrapingService:

    def __init__(
        self,
        category_scraper,
        category_pagination_service,
        product_scraper,
        product_service
    ):

        self.category_scraper = category_scraper
        self.category_pagination_service = category_pagination_service
        self.product_scraper = product_scraper
        self.product_service = product_service


    def scrape_category(
        self,
        category_url
    ):

        pages = self.category_pagination_service.get_pages(
            category_url
        )

        products = []

        for page in pages:

            urls = self.category_scraper.get_product_urls(
                page
            )

            for url in urls:

                product = self.product_scraper.scrape(
                    url
                )

                saved = self.product_service.scrape_and_save(
                    url
                )

                products.append(
                    saved
                )

        return products