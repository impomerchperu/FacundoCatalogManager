class CategoryScrapingService:
    def __init__(self, pagination_service, product_service):
        self.pagination_service = pagination_service
        self.product_service = product_service

    def scrape_category(self, category_url):

        product_links = self.pagination_service.collect_product_links(category_url)

        processed = 0

        for product_url in product_links:
            self.product_service.scrape_and_save(product_url)

            processed += 1

        return processed
