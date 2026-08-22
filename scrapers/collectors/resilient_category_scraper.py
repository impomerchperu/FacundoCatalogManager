import re

import requests

from scrapers.collectors.category_scraper import CategoryScraper


class ResilientCategoryScraper(CategoryScraper):
    """Preserva el flujo JSF y recupera categorías ante fallos transitorios."""

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
        except (RuntimeError, requests.exceptions.HTTPError) as error:
            if isinstance(
                error, requests.exceptions.HTTPError
            ) and not self._is_retryable_http_error(error):
                raise
            if (
                isinstance(error, RuntimeError)
                and "JetSmartFilters no devolvió contenido" not in str(error)
            ):
                raise

            # CategoryScraper's broad SKU regex also matches taxonomy markers
            # such as "term-127". Do not mistake those markers for products:
            # fallback pagination is only safe when the original HTML contains
            # an actual product code.
            product_keys = {
                key
                for key in self._product_keys(category_html)
                if not re.fullmatch(r"(?:TERM|PRODUCT_CAT)-\d+", key)
            }
            if product_keys:
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
                except (
                    RuntimeError,
                    requests.exceptions.HTTPError,
                ) as retry_error:
                    if isinstance(
                        retry_error,
                        requests.exceptions.HTTPError,
                    ):
                        if not self._is_retryable_http_error(retry_error):
                            raise
                    elif "JetSmartFilters no devolvió contenido" not in str(
                        retry_error
                    ):
                        raise

            raise

    @staticmethod
    def _is_retryable_http_error(error: requests.exceptions.HTTPError) -> bool:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        return status_code == 429 or (
            isinstance(status_code, int) and status_code >= 500
        )
