from scrapers.collectors.category_scraper import CategoryScraper


class ResilientCategoryScraper(CategoryScraper):
    """Preserva el flujo JSF y recupera categorías cuando el AJAX queda vacío."""

    EMPTY_JSF_RETRIES = 2

    def get_category_pages(
        self, category_url: str, expected_count: int = 0
    ) -> list[str]:
        try:
            return super().get_category_pages(category_url, expected_count)
        except RuntimeError as error:
            if "JetSmartFilters no devolvió contenido" not in str(error):
                raise

            category_html = self.get_html(category_url)
            if category_html and self._product_keys(category_html):
                return self._fallback_category_pages(
                    category_url,
                    category_html,
                    expected_count,
                )

            for _ in range(self.EMPTY_JSF_RETRIES):
                try:
                    return super().get_category_pages(
                        category_url,
                        expected_count,
                    )
                except RuntimeError as retry_error:
                    if "JetSmartFilters no devolvió contenido" not in str(
                        retry_error
                    ):
                        raise

            raise error
