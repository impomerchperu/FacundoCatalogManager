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
        self._detail_skipped = 0
        self._detail_metrics_lock = Lock()
        self._detail_executor = ThreadPoolExecutor(max_workers=self.max_workers)

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
        if self.detail_extractor is None or not products:
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

        results = list(products)
        futures: list[tuple[int, Future[Any]]] = []
        for index, (card, page_url, product) in enumerate(products):
            if self._has_structured_card_color_stock(card, product):
                product.url = self._card_detail_url(card, page_url, product)
                with self._detail_metrics_lock:
                    self._detail_skipped += 1
                continue

            futures.append(
                (
                    index,
                    self._detail_executor.submit(
                        self._enrich_from_detail_page,
                        card,
                        page_url,
                        product,
                        category_name,
                    ),
                )
            )

        for index, future in futures:
            results[index] = (
                products[index][0],
                products[index][1],
                future.result(),
            )

        return [
            product if not isinstance(product, tuple) else product[2]
            for product in results
        ]

    @staticmethod
    def _has_structured_card_color_stock(card: Any, product: Any) -> bool:
        """Evita el detalle solo con stock por color estructurado y completo."""
        color_stock = dict(getattr(product, "color_stock", {}) or {})
        if not color_stock:
            return False

        variation = card.select_one(".variaciones-producto")
        if variation is None:
            return False

        structured_colors = variation.select(
            "[data-color], [data-value], [title], .color, "
            ".color-name, .swatch",
        )
        if not structured_colors:
            return False

        stock_values = ProductCollectionScraper._stock_values(card)
        if len(color_stock) != len(stock_values):
            return False

        return ProductCollectionScraper._has_structured_stock_attributes(
            structured_colors,
        ) or ProductCollectionScraper._has_labeled_stock_values(variation)

    @staticmethod
    def _has_structured_stock_attributes(elements: Iterable[Any]) -> bool:
        """Indica si algún selector de color expone stock mediante atributos."""
        stock_keys = (
            "data-stock",
            "data-quantity",
            "data-max-qty",
            "data-max_quantity",
        )
        return any(
            any(element.get(key) not in (None, "") for key in stock_keys)
            for element in elements
        )

    @staticmethod
    def _has_labeled_stock_values(variation: Any) -> bool:
        """Indica si la variación contiene pares explícitos color:stock."""
        for paragraph in variation.select("p"):
            text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True))
            if re.match(r"^.+?\s*[:\-]\s*\d+\s*$", text):
                return True
        return False

    @staticmethod
    def _card_detail_url(card: Any, page_url: str, product: Any) -> str:
        """Construye la URL absoluta sin realizar una petición HTTP."""
        link = card.select_one('a[href*="/producto/"]')
        href = link.get("href") if link else ""
        if isinstance(href, str) and href:
            return urljoin(page_url, href)
        return str(getattr(product, "url", ""))

    @staticmethod
    def _has_complete_card_color_stock(card: Any, product: Any) -> bool:
        """Evita el detalle cuando la tarjeta ya trae color y stock alineados."""
        color_stock = dict(getattr(product, "color_stock", {}) or {})
        if not color_stock:
            return False

        stock_values: list[int] = []
        for element in card.select(".variaciones-producto p"):
            text = element.get_text(strip=True)
            if text.isdigit():
                stock_values.append(int(text))

        if not stock_values:
            text = card.get_text(" ", strip=True)
            match = re.search(
                r"stock\s+disponible\s*((?:\d[\d,.]*\s*)+)",
                text,
                flags=re.IGNORECASE,
            )
            if match is not None:
                for raw_value in re.findall(r"\d[\d,.]*", match.group(1)):
                    try:
                        stock_values.append(
                            int(float(raw_value.replace(",", "")))
                        )
                    except ValueError:
                        continue

        return len(color_stock) == len(stock_values)

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
        """Prioriza el código real del producto y usa la tarjeta como respaldo."""
        product_code = str(getattr(product, "code", "")).strip()
        if product_code:
            return f"code:{product_code.casefold()}"

        try:
            elements = card.select(
                "p.brxe-a26f34, p.brxe-heading, span.sku, [sku], [data-sku]"
            )
        except AttributeError:
            elements = []

        for element in elements:
            candidates = [
                element.get_text(" ", strip=True),
                str(element.get("sku", "")),
                str(element.get("data-sku", "")),
            ]
            for candidate in candidates:
                normalized = str(candidate).strip()
                if normalized:
                    return f"code:{normalized.casefold()}"

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
        except Exception as exc:
            with self._detail_cache_lock:
                self._detail_cache.pop(detail_key, None)
            future.set_exception(exc)
            raise
        else:
            future.set_result(detailed_product)
            return detailed_product

    def get_detail_metrics(self) -> dict[str, int]:
        """Devuelve métricas acumuladas de páginas de detalle y caché."""
        with self._detail_metrics_lock:
            return {
                "detail_requests": self._detail_requests,
                "detail_cache_hits": self._detail_cache_hits,
                "detail_cache_size": len(self._detail_cache),
                "detail_skipped": self._detail_skipped,
            }

    def reset_detail_metrics(self) -> None:
        """Reinicia métricas y caché antes de una nueva ejecución completa."""
        with self._detail_cache_lock:
            self._detail_cache.clear()
        with self._detail_metrics_lock:
            self._detail_requests = 0
            self._detail_cache_hits = 0
            self._detail_skipped = 0

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
