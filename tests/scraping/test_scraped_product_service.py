from services.scraping.scraped_product_service import ScrapedProductService
from models.scraping.scraped_product import ScrapedProduct


class FakeRepository:

    def __init__(self):
        self.products = {}


    def get_by_url(self, url):
        return self.products.get(url)


    def create(self, product):
        self.products[product.url] = product



class FakeScraper:

    def scrape(self, url):
        class Soup:

            title = type(
                "Title",
                (),
                {
                    "text": "Producto Demo"
                }
            )()

        return Soup()



class FakeMapper:

    def map(self, soup, url):

        return ScrapedProduct(
            source="test",
            url=url,
            name=soup.title.text
        )



def test_scrape_and_save_product():

    repository = FakeRepository()

    service = ScrapedProductService(
        repository,
        FakeScraper(),
        FakeMapper()
    )


    result = service.scrape_and_save(
        "https://example.com/producto"
    )


    assert result.name == "Producto Demo"

    stored = repository.get_by_url(
        "https://example.com/producto"
    )

    assert stored is not None