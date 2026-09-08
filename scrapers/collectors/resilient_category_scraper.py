import re

import requests

from scrapers.collectors.category_scraper import CategoryScraper


class ResilientCategoryScraper(CategoryScraper):
    """Preserva el flujo JSF y recupera categorías ante fallos transitorios."""

    EMPTY_JSF_RETRIES = 1

    def get_category_pages(
        self, category_url: str, expected_count: int = 0
    ) -> list[str]:
        category_html = self.get_html(category_url)
        self._cache_category_html(category_url, category_html)

        pages = self._get_pages_or_none(
            category_url,
            category_html,
            expected_count,
        )
        product_keys = self._product_keys_without_taxonomy_markers(category_html)
        if product_keys and pages == []:
            return self._fallback_after_jsf_failure(
                category_url,
                category_html,
                expected_count,
            ) or [category_url]
        if pages is not None:
            return pages

        if product_keys:
            return self._fallback_pages_or_category(
                category_url,
                category_html,
                expected_count,
            )

        return self._retry_empty_jsf_result(
            category_url,
            category_html,
            expected_count,
        )

    def _get_pages_or_none(
        self,
        category_url: str,
        category_html: str,
        expected_count: int,
    ) -> list[str] | None:
        try:
            pages = super().get_category_pages(category_url, expected_count)
        except (RuntimeError, requests.exceptions.HTTPError) as error:
            self._raise_if_not_retryable(error)
            return self._fallback_after_jsf_failure(
                category_url,
                category_html,
                expected_count,
            )

        if self._is_empty_jsf_result(category_url, category_html, pages):
            product_keys = self._product_keys_without_taxonomy_markers(category_html)
            if product_keys:
                return self._fallback_pages_or_category(
                    category_url,
                    category_html,
                    expected_count,
                )
            return None
        return pages

    def _fallback_after_jsf_failure(
        self,
        category_url: str,
        category_html: str,
        expected_count: int,
    ) -> list[str] | None:
        """Usa el HTML ya recuperado cuando JSF falla de forma reintentable."""
        product_keys = self._product_keys_without_taxonomy_markers(category_html)
        if not product_keys:
            return None
        if expected_count <= 0:
            self._cache_category_html(category_url, category_html)
            return [category_url]
        return self._fallback_pages_or_category(
            category_url,
            category_html,
            expected_count,
        )

    def _fallback_pages_or_category(
        self,
        category_url: str,
        category_html: str,
        expected_count: int,
    ) -> list[str]:
        pages = self._fallback_category_pages(
            category_url,
            category_html,
            expected_count,
        )
        return pages or [category_url]

    def _retry_empty_jsf_result(
        self,
        category_url: str,
        category_html: str,
        expected_count: int,
    ) -> list[str]:
        for _ in range(self.EMPTY_JSF_RETRIES):
            self._cache_category_html(category_url, category_html)
            try:
                pages = super().get_category_pages(category_url, expected_count)
            except requests.exceptions.HTTPError as error:
                self._raise_if_not_retryable(error)
                return self._refresh_and_fallback(
                    category_url,
                    expected_count,
                )
            except RuntimeError as error:
                self._raise_if_not_retryable(error)
                continue

            if not self._is_empty_jsf_result(category_url, category_html, pages):
                return pages

        fallback_html = self._refresh_category_html_for_fallback(category_url)
        if fallback_html:
            fallback_products = self._product_keys_without_taxonomy_markers(
                fallback_html,
            )
            if fallback_products:
                return self._fallback_pages_or_category(
                    category_url,
                    fallback_html,
                    expected_count,
                )

        # One category may be unavailable even after recovery attempts. Return
        # no pages so the full run can continue and coverage/pruning guards can
        # correctly mark the run as incomplete.
        return []

    def _refresh_and_fallback(
        self,
        category_url: str,
        expected_count: int,
    ) -> list[str]:
        """Hace un GET fresco y conserva la paginación pública disponible."""
        fallback_html = self._refresh_category_html_for_fallback(category_url)
        if not fallback_html:
            return []
        if not self._product_keys_without_taxonomy_markers(fallback_html):
            return []
        return self._fallback_pages_or_category(
            category_url,
            fallback_html,
            expected_count,
        )

    def _refresh_category_html_for_fallback(self, category_url: str) -> str:
        """Actualiza el HTML por GET antes de abandonar la vía JSF."""
        with self._category_html_cache_lock:
            self._category_html_cache.pop(category_url, None)
        try:
            html = self.get_html(category_url)
        except requests.RequestException:
            return ""
        if html:
            self._cache_category_html(category_url, html)
        return html

    def _is_empty_jsf_result(
        self,
        category_url: str,
        category_html: str,
        pages: list[str],
    ) -> bool:
        if not self._is_facundo_url(category_url):
            return False
        return (
            not self._product_keys_without_taxonomy_markers(category_html)
            and pages == [category_url]
        )

    def _raise_if_not_retryable(
        self,
        error: RuntimeError | requests.exceptions.HTTPError,
    ) -> None:
        if isinstance(error, requests.exceptions.HTTPError):
            if not self._is_retryable_http_error(error):
                raise error
            return
        if "JetSmartFilters no devolvió contenido" not in str(error):
            raise error

    def _product_keys_without_taxonomy_markers(
        self,
        category_html: str,
    ) -> set[str]:
        return {
            key
            for key in self._product_keys(category_html)
            if not re.fullmatch(r"(?:TERM|PRODUCT_CAT)-\d+", key)
        }

    @staticmethod
    def _is_retryable_http_error(error: requests.exceptions.HTTPError) -> bool:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        return status_code == 429 or (
            isinstance(status_code, int) and status_code >= 500
        )
