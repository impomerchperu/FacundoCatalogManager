import json
from types import SimpleNamespace

import pytest

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
    scraper.PRODUCTS_PER_PAGE = 1

    pages = scraper.get_category_pages(url, expected_count=2)

    assert pages == [url, page_two]


def test_category_scraper_tries_public_query_variant_when_wordpress_page_repeats():
    url = "https://stock.importacionesfacundo.com/categoria-producto/antiestres/"
    page_two = f"{url}?product-page=2"
    browser = FakeBrowser({
        url: '<article><a href="/producto/p1/"></a></article>',
        f"{url}page/2/": '<article><a href="/producto/p1/"></a></article>',
        page_two: '<article><a href="/producto/p2/"></a></article>',
    })
    scraper = CategoryScraper(browser)
    scraper.PRODUCTS_PER_PAGE = 1

    pages = scraper.get_category_pages(url, expected_count=2)

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
    scraper.PRODUCTS_PER_PAGE = 1

    pages = scraper.get_category_pages(url, expected_count=2)

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


def test_category_scraper_exposes_jsf_rendered_page_through_get_html():
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/articulos-de-antiestres/"
    page_two = f"{category_url.rstrip('/')}?product-page=2"
    browser = FakeBrowser({
        category_url: '<body class="term-123"></body>',
    })
    scraper = CategoryScraper(browser)

    def fake_post_jsf(payload):
        page = next(value for key, value in payload if key == "paged")
        rendered = (
            '<article>FB-1000 producto-1</article>'
            if page == "1"
            else '<article>FB-1001 producto-2</article>'
        )
        return json.dumps({
            "data": {
                "found_posts": 50,
                "max_num_pages": 2,
                "rendered_content": rendered,
            }
        })

    scraper._post_jsf = fake_post_jsf

    pages = scraper.get_category_pages(category_url, expected_count=50)

    assert pages == [category_url, page_two]
    assert scraper.get_html(page_two) == (
        '<article>FB-1001 producto-2</article>'
    )


def test_category_pagination_raises_when_jsf_repeats_product_urls():
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/articulos-de-antiestres/"
    browser = FakeBrowser({
        category_url: '<body class="term-123"></body>',
    })
    scraper = CategoryScraper(browser)
    calls = {"count": 0}

    def fake_post_jsf(payload):
        page = next(value for key, value in payload if key == "paged")
        calls["count"] += 1
        if page == "1":
            rendered = '<article><a href="/producto/p1/"></a></article>'
        else:
            rendered = (
                '<article><a href="/producto/p1/"></a></article>'
                '<script>FB-UNRELATED-999</script>'
            )
        return json.dumps({
            "data": {
                "found_posts": 50,
                "max_num_pages": 2,
                "rendered_content": rendered,
            }
        })

    scraper._post_jsf = fake_post_jsf

    with pytest.raises(RuntimeError, match="Repeated JSF pagination page 2"):
        scraper.get_category_pages(category_url, expected_count=50)

    assert calls["count"] == 2
