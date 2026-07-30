from models.scraping.scraped_product import ScrapedProduct


class ScrapedProductService:

    def __init__(
        self,
        repository,
        scraper,
        mapper
    ):
        self.repository = repository
        self.scraper = scraper
        self.mapper = mapper


    def scrape_and_save(
        self,
        url
    ):

        existing = self.repository.get_by_url(
            url
        )

        if existing:
            return existing


        soup = self.scraper.scrape(
            url
        )


        product = self.mapper.map(
            soup,
            url
        )


        self.repository.create(
            product
        )


        return product