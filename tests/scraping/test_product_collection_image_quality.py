from bs4 import BeautifulSoup

from models.scraping.scraped_product import ScrapedProduct
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


def test_product_collection_requests_detail_for_generic_image():
    card = BeautifulSoup(
        """
        <article>
            <a href="/producto/gota-antiestres/">
                <img src="https://site.test/uploads/Logo-Facundo-2026.webp">
            </a>
            <p class="brxe-a26f34">FB-4010</p>
            <h2 class="brxe-f31760">Gota Antiestrés</h2>
            <div class="variaciones-producto">
                <p>25</p>
            </div>
        </article>
        """,
        "html.parser",
    )
    product = ScrapedProduct(
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/uploads/Logo-Facundo-2026.webp",
    )

    reason = ProductCollectionScraper._detail_skip_reason(card, product)

    assert reason == "image_quality"


def test_product_collection_does_not_request_detail_for_valid_image():
    card = BeautifulSoup(
        """
        <article>
            <a href="/producto/gota-antiestres/">
                <img src="https://site.test/uploads/SFPU-40-main.webp">
            </a>
            <p class="brxe-a26f34">FB-4010</p>
            <h2 class="brxe-f31760">Gota Antiestrés</h2>
            <div class="variaciones-producto">
                <p>25</p>
            </div>
        </article>
        """,
        "html.parser",
    )
    product = ScrapedProduct(
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/uploads/SFPU-40-main.webp",
    )

    reason = ProductCollectionScraper._detail_skip_reason(card, product)

    assert reason == "complete_single_stock"
