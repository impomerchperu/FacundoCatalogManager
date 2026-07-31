from scrapers.selectors.pagination_selectors import PaginationSelectors


class PaginationExtractor:

    def get_next_page(
        self,
        soup
    ):

        link = soup.select_one(
            PaginationSelectors.NEXT_PAGE
        )

        if link:
            return link.get(
                "href"
            )

        return None