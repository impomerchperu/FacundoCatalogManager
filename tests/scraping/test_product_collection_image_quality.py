import pytest
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
        description="Descripción de prueba.",
        image_url="https://site.test/uploads/Logo-Facundo-2026.webp",
    )

    reason = ProductCollectionScraper._detail_request_reason(card, product)

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
        description="Descripción de prueba.",
        image_url="https://site.test/uploads/SFPU-40-main.webp",
    )

    reason = ProductCollectionScraper._detail_skip_reason(card, product)

    assert reason == "complete_single_stock"


@pytest.mark.parametrize("code", ["FB-3017", "FB-3018"])
def test_product_collection_forces_detail_for_known_bad_card_images(code):
    product = ScrapedProduct(
        code=code,
        name="Plancha Transfer",
        description="Descripción de prueba.",
        image_url="https://site.test/uploads/valid-looking-image.webp",
    )

    assert ProductCollectionScraper._image_needs_detail(product) is True



class FakeDetailCategoryScraper:
    def get_html(self, url):
        self.url = url
        return "<html></html>"


class FakeDetailExtractor:
    def extract(self, soup, url="", category=""):
        del soup
        product = ScrapedProduct(
            code="FB-3017",
            name="Plancha Transfer",
            description="Descripción de detalle.",
            image_url="https://site.test/uploads/correct-detail.webp",
        )
        product.image_candidates = [
            {
                "url": "https://site.test/uploads/correct-detail.webp",
                "score": 1000,
                "exact_code": False,
                "generic": False,
                "gallery": True,
            }
        ]
        return product


def test_forced_detail_marks_authoritative_image_candidate():
    category_scraper = FakeDetailCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=None,
        product_extractor=None,
        detail_extractor=FakeDetailExtractor(),
        max_workers=1,
    )
    card = BeautifulSoup(
        '<a href="/producto/plancha-38x38/"><img src="https://site.test/uploads/wrong.webp"></a>',
        "html.parser",
    )
    product = ScrapedProduct(
        code="FB-3017",
        name="Plancha Transfer",
        description="Descripción.",
        image_url="https://site.test/uploads/wrong.webp",
    )

    try:
        result = scraper._enrich_from_detail_page(
            card,
            "https://site.test/categoria/",
            product,
            "Máquinas de sublimación",
        )
    finally:
        scraper.close()

    assert result.image_url == "https://site.test/uploads/correct-detail.webp"
    assert result.image_candidates[0]["authoritative"] is True
