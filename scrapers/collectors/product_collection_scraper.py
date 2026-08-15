import re
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config.scraping_config import SCRAPING_MAX_WORKERS
from models.scraping.category import Category


class ProductCollectionScraper:
    """Recorre todas las páginas de una categoría y extrae sus productos."""

    def __init__(
        self,
        category_scraper: Any,
        card_extractor: Any,
        product_extractor: Any,
        detail_extractor: Any = None,
        max_workers: int = SCRAPING_MAX_WORKERS,
    ):
        self.category_scraper = category_scraper
        self.card_extractor = card_extractor
        self.product_extractor = product_extractor
        self.detail_extractor = detail_extractor
        self.max_workers = max(1, max_workers)
        self._detail_cache: dict[str, Future[Any]] = {}
        self._detail_cache_lock = Lock()
        self._detail_requests = 0
        self._detail_cache_hits = 0
        self._detail_metrics_lock = Lock()

    def scrape_category(self, category: Any) -> list[Any]:
        """Extrae todos los productos de una categoría."""
        if isinstance(category, Category):
            category_url = category.url
            category_name = category.name
        else:
            category_url = category
            category_name = ""

        products: list[Any] = []
        pages = self.category_scraper.get_category_pages(category_url)

        for page in pages:
            html = self.category_scraper.get_html(page)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            cards = self._extract_cards(soup)

            page_products = []
            for card in cards:
                product = self.product_extractor.extract(
                    card,
                    url="",
                    category=category_name,
                )
                page_products.append((card, page, product))

            products.extend(
                self._enrich_products(
                    page_products,
                    category_name,
                )
            )

        return products

    def _enrich_products(
        self,
        products: list[tuple[Any, str, Any]],
        category_name: str,
    ) -> list[Any]:
        """Enriquece páginas de detalle en paralelo y conserva el orden."""
        if self.detail_extractor is None or len(products) <= 1:
            return [
                self._enrich_from_detail_page(
                    card,
                    page_url,
                    product,
                    category_name,
                )
                for card, page_url, product in products
            ]

        browser = getattr(self.category_scraper, "browser", None)
        if browser is not None and hasattr(browser, "enable_thread_sessions"):
            browser.enable_thread_sessions()

        worker_count = min(self.max_workers, len(products))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    self._enrich_from_detail_page,
                    card,
                    page_url,
                    product,
                    category_name,
                )
                for card, page_url, product in products
            ]
            return [future.result() for future in futures]

    def _extract_cards(self, soup: Any) -> list[Any]:
        if callable(self.card_extractor):
            cards = self.card_extractor(soup)
        else:
            cards = self.card_extractor.extract(soup)
        if not isinstance(cards, Iterable):
            raise TypeError("El extractor de tarjetas debe devolver un iterable.")
        return list(cards)

    def _enrich_from_detail_page(
        self,
        card: Any,
        page_url: str,
        product: Any,
        category_name: str,
    ) -> Any:
        """Completa colores y stock desde la página de detalle."""
        if self.detail_extractor is None:
            return product

        link = card.select_one('a[href*="/producto/"]')
        href = link.get("href") if link else ""
        if not isinstance(href, str) or not href:
            return product

        detail_url = urljoin(page_url, href)
        detail_key = self._detail_cache_key(card, product, detail_url)
        detailed_product = self._get_detailed_product(
            detail_key,
            detail_url,
            category_name,
        )
        if detailed_product is None:
            return product

        detail_color_stock = dict(
            getattr(detailed_product, "color_stock", {})
        )
        card_stock_values = self._stock_values(card)

        if detail_color_stock:
            colors = list(detail_color_stock)
            if len(card_stock_values) == len(colors):
                product.color_stock = dict(
                    zip(colors, card_stock_values, strict=True),
                )
                product.stock = sum(product.color_stock.values())
            elif sum(detail_color_stock.values()) > 0:
                product.color_stock = detail_color_stock
                product.stock = sum(detail_color_stock.values())
            elif not card_stock_values:
                product.color_stock = {}
            product.url = detail_url
            return product

        if product.color_stock:
            product.url = detail_url

        return product

    @staticmethod
    def _detail_cache_key(card: Any, product: Any, detail_url: str) -> str:
        """Usa el código del producto; el código de la tarjeta es respaldo."""
        candidates = [getattr(product, "code", "")]
        try:
            element = card.select_one(
                "p.brxe-a26f34, p.brxe-heading, span.sku, [sku]"
            )
        except AttributeError:
            element = None
        if element is not None:
            candidates.append(element.get_text(" ", strip=True))
            for attribute in ("sku", "data-sku"):
                candidates.append(str(element.get(attribute, "")))

        for candidate in candidates:
            normalized = str(candidate).strip()
            if not normalized:
                continue
            match = re.search(r"\b[A-Z]{1,5}-[A-Z0-9][A-Z0-9._-]*\b", normalized)
            if match:
                return f"code:{match.group(0).upper()}"

        return f"url:{detail_url}"

    def _get_detailed_product(
        self,
        detail_key: str,
        detail_url: str,
        category_name: str,
    ):
        """Obtiene el detalle una sola vez por código, incluso entre categorías."""
        owner = False
        with self._detail_cache_lock:
            future = self._detail_cache.get(detail_key)
            if future is None:
                future = Future()
                self._detail_cache[detail_key] = future
                owner = True
            else:
                with self._detail_metrics_lock:
                    self._detail_cache_hits += 1

        if not owner:
            return future.result()

        with self._detail_metrics_lock:
            self._detail_requests += 1

        try:
            detail_html = self.category_scraper.get_html(detail_url)
            if not detail_html:
                future.set_result(None)
                return None

            detail_soup = BeautifulSoup(detail_html, "html.parser")
            detailed_product = self.detail_extractor.extract(
                detail_soup,
                url=detail_url,
                category=category_name,
            )
            future.set_result(detailed_product)
            return detailed_product
        except Exception as exc:
            with self._detail_cache_lock:
                self._detail_cache.pop(detail_key, None)
            future.set_exception(exc)
            raise

    def get_detail_metrics(self) -> dict[str, int]:
        """Devuelve métricas acumuladas de páginas de detalle y caché."""
        with self._detail_metrics_lock:
            return {
                "detail_requests": self._detail_requests,
                "detail_cache_hits": self._detail_cache_hits,
                "detail_cache_size": len(self._detail_cache),
            }

    def reset_detail_metrics(self) -> None:
        """Reinicia las métricas sin borrar el caché de productos."""
        with self._detail_metrics_lock:
            self._detail_requests = 0
            self._detail_cache_hits = 0

    @staticmethod
    def _stock_values(card: Any) -> list[int]:
        """Extrae existencias de la tarjeta, incluyendo el bloque textual visible."""
        values: list[int] = []
        for element in card.select(".variaciones-producto p"):
            text = element.get_text(strip=True)
            if text.isdigit():
                values.append(int(text))
        if values:
            return values

        text = card.get_text(" ", strip=True)
        match = re.search(
            r"stock\s+disponible\s*((?:\d[\d,.]*\s*)+)",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            return []

        result: list[int] = []
        for raw_value in re.findall(r"\d[\d,.]*", match.group(1)):
            try:
                result.append(int(float(raw_value.replace(",", ""))))
            except ValueError:
                continue
        return result
