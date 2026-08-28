from types import SimpleNamespace

from models.scraping.category import Category
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


class FakeBrowser:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url):
        return self.pages.get(url, "")


def test_category_scraper_discovers_real_woocommerce_page_variant_from_expected_count():
    url = "https://example.test/categoria-producto/antiestres/"
    page_two = f"{url}page/2/"
    browser = FakeBrowser({
        url: "<article>FB-1000-AZ producto 1</article>",
        page_two: "<article>FB-1001-AZ producto 2</article>",
    })
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(url, expected_count=50)

    assert pages == [url, page_two]


def test_category_scraper_respects_explicit_pagination_href():
    url = "https://example.test/categoria-producto/antiestres/"
    page_two = f"{url}?product-page=2"
    browser = FakeBrowser({
        url: (
            '<article>FB-1000-AZ producto 1</article>'
            '<nav class="woocommerce-pagination">'
            f'<a class="page-numbers" href="{page_two}">2</a>'
            "</nav>"
        ),
        page_two: "<article>FB-1001-AZ producto 2</article>",
    })
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(url, expected_count=50)

    assert pages == [url, page_two]


def test_product_collection_deduplicates_same_product_returned_by_page_variants():
    category_url = "https://example.test/categoria-producto/antiestres/"
    page_two = f"{category_url}page/2/"
    query_two = f"{category_url}?product-page=2"

    class FakeCategoryScraper:
        browser = None

        def get_category_pages(self, url, expected_count=0):
            assert url == category_url
            assert expected_count == 50
            return [category_url, page_two, query_two]

        def get_html(self, url):
            return {
                category_url: '<article><a href="/producto/p1/"></a></article>',
                page_two: '<article><a href="/producto/p2/"></a></article>',
                query_two: '<article><a href="/producto/p2/"></a></article>',
            }[url]

    def card_extractor(soup):
        return soup.select("article")

    def product_extractor(card, *, url, category):
        href = card.select_one("a")["href"]
        code = href.rstrip("/").split("/")[-1].upper()
        return SimpleNamespace(
            code=code,
            name=code,
            category=category,
            url=url,
            description="",
            image_url="",
            price_sample=0,
            price_hundred=0,
            price_thousand=0,
            stock=0,
            color_stock={},
        )

    collection = ProductCollectionScraper(
        category_scraper=FakeCategoryScraper(),
        card_extractor=card_extractor,
        product_extractor=product_extractor,
    )

    products = collection.collect_category(Category(
        name="Artículos Antiestrés",
        url=category_url,
        expected_count=50,
    ))

    assert [product.code for _, _, product in products] == ["P1", "P2"]
