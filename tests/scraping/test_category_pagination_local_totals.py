import json

from scrapers.collectors.category_scraper import CategoryScraper


class FakeBrowser:
    def __init__(self, responses):
        self.responses = responses
        self.post_calls = []

    def get(self, url):
        return self.responses.get(url, "<html></html>")

    def post(self, url, data=None):
        self.post_calls.append(data)
        page = next(value for key, value in data if key == "paged")
        return self.responses[f"ajax:{page}"]


class FakeProductBlockExtractor:
    def extract(self, soup):
        return soup.select("article.product")


def products(start, count):
    return "".join(
        (
            f'<article class="product"><a href="/producto/p{number}/">'
            f"<span class=\"sku\">P{number}</span>"
            "</a></article>"
        )
        for number in range(start, start + count)
    )


def jsf_response(start, count, found_posts, max_num_pages):
    return json.dumps(
        {
            "pagination": {
                "found_posts": found_posts,
                "max_num_pages": max_num_pages,
            },
            "rendered_content": products(start, count),
        }
    )


def test_facundo_discovers_all_pages_from_jsf_when_no_expected_count_is_given():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: (
            '<html><body class="product_cat-127">'
            + products(1, 25)
            + "</body></html>"
        ),
        "ajax:1": jsf_response(1, 25, 51, 3),
        "ajax:2": jsf_response(26, 25, 51, 3),
        "ajax:3": jsf_response(51, 1, 51, 3),
    }
    scraper = CategoryScraper(
        FakeBrowser(responses),
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]
