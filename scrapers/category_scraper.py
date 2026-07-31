class CategoryScraper:

    def __init__(
        self,
        browser,
        parser,
        product_link_extractor=None
    ):

        self.browser = browser
        self.parser = parser
        self.product_link_extractor = product_link_extractor


    def scrape(
        self,
        url
    ):

        html = self.browser.get(url)

        return self.parser.extract_categories(
            html
        )


    def get_product_urls(
        self,
        url
    ):

        html = self.browser.get(url)

        soup = self.parser.parse(
            html
        )

        return self.product_link_extractor.extract(
            soup
        )