from scrapers.collectors.category_scraper import CategoryScraper


class ResilientCategoryScraper(CategoryScraper):
    """Preserva el flujo JSF y recupera categorías cuando el AJAX queda vacío."""

    EMPTY_JSF_RETRIES = 2

    def get_category_pages(
        self, category_url: str, expected_count: int = 0
    ) -> list[str]:
        # Preserve the original category HTML across retries. CategoryScraper
        # consumes its cache entry on each get_html() call; without restoring
        # it, a retry can lose the term ID and silently switch to the fallback
        # paginator instead of retrying JetSmartFilters.
        category_html = self.get_html(category_url)
        self._cache_category_html(category_url, category_html)

        try:
            return super().get_category_pages(category_url, expected_count)
        except RuntimeError as error:
            if "JetSmartFilters no devolvió contenido" not in str(error):
                raise

            if category_html and self._product_keys(category_html):
                return self._fallback_category_pages(
                    category_url,
                    category_html,
                    expected_count,
                )

            for _ in range(self.EMPTY_JSF_RETRIES):
                self._cache_category_html(category_url, category_html)
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

            raise
