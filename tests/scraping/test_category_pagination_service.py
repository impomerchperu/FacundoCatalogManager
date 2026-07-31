from services.scraping.category_pagination_service import (
    CategoryPaginationService
)


class FakePagination:

    def get_pages(self, url):

        return [
            "html_page_1",
            "html_page_2"
        ]


class FakeLinkExtractor:

    def extract(self, html):

        if html == "html_page_1":
            return [
                "product_1",
                "product_2"
            ]

        return [
            "product_2",
            "product_3"
        ]


def test_collect_product_links():

    service = CategoryPaginationService(
        FakePagination(),
        FakeLinkExtractor()
    )

    result = service.collect_product_links(
        "category_url"
    )

    assert len(result) == 3

    assert "product_1" in result
    assert "product_2" in result
    assert "product_3" in result