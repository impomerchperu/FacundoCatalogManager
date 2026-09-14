import re

import requests

from scrapers.collectors.category_pagination_engine import _collect_direct_pages
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
        if pages == []:
            refreshed = self._refresh_and_fallback(
                category_url,
                expected_count,
            )
            if refreshed:
                return refreshed
            return []

        product_keys = self._product_keys_without_taxonomy_markers(category_html)
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
        except (RuntimeError, requests.exceptions.RequestException) as error:
            cached_pages = self._recover_cached_jsf_pages(
                category_url,
                expected_count,
            )
            if cached_pages is not None:
                return cached_pages
            if isinstance(error, requests.exceptions.HTTPError):
                self._raise_if_not_retryable(error)
            else:
                raise
            return self._refresh_and_fallback(
                category_url,
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

    def _recover_cached_jsf_pages(
        self,
        category_url: str,
        expected_count: int,
    ) -> list[str] | None:
        """Return already validated JSF pages when only the optional boundary probe fails."""
        required_pages = self._required_page_count(expected_count)
        if required_pages <= 0:
            return None
        with self._jsf_cache_lock:
            cached = [
                page_number
                for page_number in range(1, required_pages + 1)
                if self._jsf_page_cache.get((category_url, page_number))
            ]
        if len(cached) != required_pages:
            return None
        return [
            category_url,
            *(
                self._jsf_page_url(category_url, page_number)
                for page_number in range(2, required_pages + 1)
            ),
        ]

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
        """Recover public pages while validating known coverage strictly."""
        if self._is_facundo_url(category_url):
            if expected_count <= 0:
                pages = self._fallback_category_pages(
                    category_url,
                    category_html,
                    expected_count,
                )
                return pages or [category_url]
            try:
                pages, _ = _collect_direct_pages(
                    self,
                    category_url,
                    category_html,
                    expected_count,
                )
            except (RuntimeError, TypeError, ValueError):
                return [category_url]
            return pages or [category_url]

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

        return self._refresh_and_fallback(category_url, expected_count)

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
