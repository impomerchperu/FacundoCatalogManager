from models.scraping.scraped_product import ScrapedProduct


class ScrapedProductMapper:

    def map(
        self,
        soup,
        url
    ):

        title = ""

        if soup.title:
            title = soup.title.text.strip()


        return ScrapedProduct(
            source="web",
            url=url,
            name=title
        )