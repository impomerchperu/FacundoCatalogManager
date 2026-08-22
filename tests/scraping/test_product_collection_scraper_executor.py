from types import SimpleNamespace

from models.scraping.category import Category
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


class SingleProductCategoryScraper:
    def get_category_pages(self, url):
        return [url]

    def get_html(self, url):
        if "/producto/" in url:
            return "<html><h1>Detalle</h1></html>"
        return """
        <article>
            <a href="/producto/demo/"><h2>Demo</h2></a>
            <p>10</p>
        </article>
        """


def test_detail_enrichment_does_not_nest_waiting_futures_in_same_executor():
    scraper = ProductCollectionScraper(
        SingleProductCategoryScraper(),
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=lambda card, url, category: SimpleNamespace(
            code="FB-1",
            name="Demo",
            description="",
            image_url="",
            price_sample=0,
            price_hundred=0,
            price_thousand=0,
            stock=10,
            color_stock={},
            url=url,
        ),
        detail_extractor=SimpleNamespace(
            extract=lambda soup, url, category: SimpleNamespace(
                color_stock={"Rojo": 10},
            )
        ),
        max_workers=1,
    )

    products = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/categoria/")
    )

    assert len(products) == 1
    assert products[0].color_stock == {"Rojo": 10}
    assert products[0].stock == 10
    assert scraper.get_detail_metrics()["detail_requests"] == 1
