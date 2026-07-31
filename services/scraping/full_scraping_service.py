class FullScrapingService:

    def __init__(
        self,
        category_scraper=None,
        category_pagination_service=None,
        product_scraper=None,
        product_service=None,
        category_service=None,
        image_manager=None,
        downloader=None
    ):

        self.category_scraper = category_scraper
        self.category_pagination_service = (
            category_pagination_service
        )

        self.product_scraper = product_scraper
        self.product_service = product_service

        self.category_service = category_service
        self.image_manager = image_manager
        self.downloader = downloader


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


    def scrape_all(
        self
    ):

        categories = self.category_service.scrape_all()


        products = self.product_scraper.scrape_products(
            categories
        )


        if self.image_manager:

            images = self.image_manager.download_all(
                products,
                self.downloader
            )

        else:

            images = []


        return {
            "categories": categories,
            "products": products,
            "images": images
        }


    def run(
        self
    ):

        categories = self.category_service.scrape_all()


        products = self.product_scraper.scrape_products(
            categories
        )


        images = []

        if self.image_manager:

            images = self.image_manager.download_all(
                products,
                self.downloader
            )


        return {
            "categories": categories,
            "products": products,
            "images": images
        }