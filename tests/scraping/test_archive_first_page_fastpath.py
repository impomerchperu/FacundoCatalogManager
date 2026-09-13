import json

from scrapers.collectors.category_scraper import CategoryScraper


class FakeBrowser:
    def __init__(self, responses):
        self.responses = responses
        self.post_pages = []

    def get(self, url):
        return self.responses.get(url, "")

    def post(self, url, data=None):
        page = next(value for key, value in data if key == "paged")
        self.post_pages.append(int(page))
        return self.responses[f"ajax:{page}"]


def products(start, count):
    return "".join(
        f'<article><a href="/producto/p{number}/">P{number}</a></article>'
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


def test_reuses_archive_first_page_and_skips_redundant_jsf_page_one():
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
        "ajax:2": jsf_response(26, 25, 51, 3),
        "ajax:3": jsf_response(51, 1, 51, 3),
        "ajax:4": "",
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url, expected_count=51)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]
    assert browser.post_pages == [2, 3, 4]


def test_reuses_single_page_archive_but_still_probes_hidden_page():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    hidden_page = products(20, 1)
    responses = {
        category_url: (
            '<html><body class="product_cat-127">'
            + products(1, 19)
            + "</body></html>"
        ),
        "ajax:2": json.dumps({"rendered_content": hidden_page}),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url, expected_count=19)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
    ]
    assert browser.post_pages == [2]
