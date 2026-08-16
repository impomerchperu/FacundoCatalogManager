import re
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, ClassVar, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config.scraping_config import SCRAPING_MAX_WORKERS
from models.scraping.category import Category


class ProductCollectionScraper:
    """Recorre todas las páginas de una categoría y extrae sus productos."""

    _PRICE_FIELDS = (
        "price_sample",
        "price_hundred",
        "price_thousand",
    )
    _PRICE_LABELS: ClassVar[dict[str, str]] = {
        "price_sample": "precio muestra",
        "price_hundred": "precio ciento",
        "price_thousand": "precio millar",
    }

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
        self._detail_reason_counts: dict[str, int] = {}
        self._detail_metrics_lock = Lock()
        self._detail_executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def scrape_category(self, category: Any) -> list[Any]:
        """Extrae todos los productos de una categoría."""
        category_name = category.name if isinstance(category, Category) else ""
        collected = self.collect_category(category)
        return self.enrich_category_products(collected, category_name)

    def collect_category(self, category: Any) -> list[tuple[Any, str, Any]]:
        """Descarga y extrae tarjetas sin solicitar páginas de detalle."""
        if isinstance(category, Category):
            category_url = category.url
            category_name = category.name
        else:
            category_url = category
            category_name = ""

        products: list[tuple[Any, str, Any]] = []
        pages = self.category_scraper.get_category_pages(category_url)

        for page in pages:
            html = self.category_scraper.get_html(page)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            cards = self._extract_cards(soup)
            for card in cards:
                product = self.product_extractor.extract(
                    card,
                    url="",
                    category=category_name,
                )
                product_url = self._card_detail_url(card, page, product)
                if product_url:
                    product.url = product_url
                products.append((card, page, product))
        return products

    def enrich_category_products(
        self,
        products: list[tuple[Any, str, Any]],
        category_name: str = "",
    ) -> list[Any]:
        """Completa las tarjetas recolectadas usando páginas de detalle."""
        return self._enrich_products(products, category_name)

    def _enrich_products(
        self,
        products: list[tuple[Any, str, Any]],
        category_name: str,
    ) -> list[Any]:
        """Enriquece páginas de detalle en paralelo y conserva el orden."""
        if self.detail_extractor is None or not products:
            return [
                self._enrich_from_detail_page(card, page_url, product, category_name)
                for card, page_url, product in products
            ]

        browser = getattr(self.category_scraper, "browser", None)
        if browser is not None and hasattr(browser, "enable_thread_sessions"):
            browser.enable_thread_sessions()

        results = list(products)
        futures: list[tuple[int, Future[Any]]] = []
        for index, (card, page_url, product) in enumerate(products):
            skip_reason = self._detail_skip_reason(card, product)
            if skip_reason is not None:
                product.url = self._card_detail_url(card, page_url, product)
                with self._detail_metrics_lock:
                    self._detail_skipped += 1
                    self._record_detail_reason(f"skipped_{skip_reason}")
                continue

            request_reason = self._detail_request_reason(card, product)
            with self._detail_metrics_lock:
                self._record_detail_reason(f"requested_{request_reason}")
                if request_reason == "missing_prices":
                    for field in self._missing_price_fields(card, product):
                        self._record_detail_reason(
                            f"requested_missing_{field.removeprefix('price_')}"
                        )
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
            results[index] = (products[index][0], products[index][1], future.result())

        return [
            product if not isinstance(product, tuple) else product[2]
            for product in results
        ]

    @classmethod
    def _detail_skip_reason(cls, card: Any, product: Any) -> str | None:
        """Explica por qué una tarjeta puede evitar la página de detalle."""
        if cls._has_complete_card_color_stock(card, product):
            return "complete_color_stock"

        stock_values = cls._stock_values(card)
        if len(stock_values) != 1:
            return None

        required_fields = ("code", "name", "description", "image_url")
        if any(
            not str(getattr(product, field, "")).strip()
            for field in required_fields
        ):
            return None
        if cls._missing_price_fields(card, product):
            return None
        return "complete_single_stock"

    @classmethod
    def _detail_request_reason(cls, card: Any, product: Any) -> str:
        """Clasifica por qué una tarjeta todavía necesita su página de detalle."""
        stock_values = cls._stock_values(card)
        if len(stock_values) != 1:
            return cls._stock_request_reason(card, stock_values)
        required_fields = ("code", "name", "description", "image_url")
        if any(
            not str(getattr(product, field, "")).strip()
            for field in required_fields
        ):
            return "missing_fields"
        if cls._missing_price_fields(card, product):
            return "missing_prices"
        return "other"

    @staticmethod
    def _stock_request_reason(card: Any, stock_values: list[int]) -> str:
        """Clasifica solicitudes según la forma visible del stock de la tarjeta."""
        if not stock_values:
            return "missing_stock"
        variation = card.select_one(".variaciones-producto")
        if variation is not None:
            labeled_values = [
                paragraph
                for paragraph in variation.select("p")
                if re.match(
                    r"^.+?\s*[:\-]\s*\d[\d,.]*\s*$",
                    paragraph.get_text(" ", strip=True),
                )
            ]
            if len(labeled_values) == len(stock_values):
                return "multiple_labeled_stock"
        return "multiple_numeric_stock"

    @classmethod
    def _missing_price_fields(cls, card: Any, product: Any) -> tuple[str, ...]:
        """Devuelve solo precios ausentes que la tarjeta realmente anuncia."""
        card_text = " ".join(card.stripped_strings).casefold()
        return tuple(
            field
            for field in cls._PRICE_FIELDS
            if float(getattr(product, field, 0.0) or 0.0) <= 0
            and cls._PRICE_LABELS[field] in card_text
        )

    @classmethod
    def _can_skip_detail(cls, card: Any, product: Any) -> bool:
        """Evita el detalle cuando la tarjeta ya contiene datos suficientes."""
        return cls._detail_skip_reason(card, product) is not None

    def _record_detail_reason(self, reason: str) -> None:
        """Acumula una clasificación de decisión de enriquecimiento."""
        self._detail_reason_counts[reason] = (
            self._detail_reason_counts.get(reason, 0) + 1
        )

    @staticmethod
    def _has_complete_card_color_stock(card: Any, product: Any) -> bool:
        """Acepta color-stock completo solo con estructura explícita de colores."""
        color_stock = dict(getattr(product, "color_stock", {}) or {})
        if not color_stock:
            return False
        stock_values = ProductCollectionScraper._stock_values(card)
        if len(color_stock) != len(stock_values) or not stock_values:
            return False
        variation = card.select_one(".variaciones-producto")
        if variation is None:
            return False

        explicit_color_nodes = variation.select(
            "[data-color], [data-value], [title], .color, .color-name, .swatch"
        )
        return bool(explicit_color_nodes)

    @staticmethod
    def _card_detail_url(card: Any, page_url: str, product: Any) -> str:
        """Construye la URL absoluta sin realizar una petición HTTP."""
        link = card.select_one('a[href*="/producto/"]')
        href = link.get("href") if link else ""
        if isinstance(href, str) and href:
            return urljoin(page_url, href)
        return str(getattr(product, "url", ""))

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
        detail_color_stock = dict(getattr(detailed_product, "color_stock", {}))
        card_stock_values = self._stock_values(card)
        if detail_color_stock:
            colors = list(detail_color_stock)
            if len(card_stock_values) == len(colors):
                product.color_stock = dict(zip(colors, card_stock_values, strict=True))
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
            card_text = " ".join(card.stripped_strings).strip().casefold()
        except AttributeError:
            card_text = ""
        return f"url:{detail_url.casefold()}|card:{card_text}"

    def _get_detailed_product(
        self,
        cache_key: str,
        detail_url: str,
        category_name: str,
    ) -> Any | None:
        with self._detail_cache_lock:
            future = self._detail_cache.get(cache_key)
            if future is not None:
                self._detail_cache_hits += 1
            else:
                self._detail_requests += 1
                future = self._detail_executor.submit(
                    self._fetch_detail_product,
                    detail_url,
                    category_name,
                )
                self._detail_cache[cache_key] = future
        try:
            return future.result()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            with self._detail_cache_lock:
                if self._detail_cache.get(cache_key) is future:
                    self._detail_cache.pop(cache_key, None)
            return None

    def _fetch_detail_product(self, detail_url: str, category_name: str) -> Any | None:
        html = self.category_scraper.get_html(detail_url)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        return self.detail_extractor.extract(
            soup,
            url=detail_url,
            category=category_name,
        )

    @staticmethod
    def _stock_values(card: Any) -> list[int]:
        """Extrae el stock de la tarjeta, incluyendo la secuencia tras su etiqueta."""
        values: list[int] = []
        variation = card.select_one(".variaciones-producto")
        if variation is not None:
            for paragraph in variation.select("p"):
                text = paragraph.get_text(" ", strip=True)
                numbers = re.findall(r"\d[\d,.]*", text)
                if numbers:
                    try:
                        values.append(
                            int(float(numbers[-1].replace(",", "")))
                        )
                    except ValueError:
                        continue
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

        for raw_value in re.findall(r"\d[\d,.]*", match.group(1)):
            try:
                values.append(int(float(raw_value.replace(",", ""))))
            except ValueError:
                continue
        return values

    def reset_detail_metrics(self) -> None:
        """Reinicia métricas y cache para comenzar una nueva corrida completa."""
        with self._detail_cache_lock:
            self._detail_cache.clear()
            self._detail_requests = 0
            self._detail_cache_hits = 0
        with self._detail_metrics_lock:
            self._detail_skipped = 0
            self._detail_reason_counts.clear()

    def get_detail_metrics(self) -> dict[str, Any]:
        """Devuelve métricas de cache y clasificación de detalle."""
        with self._detail_cache_lock:
            detail_requests = self._detail_requests
            detail_cache_hits = self._detail_cache_hits
            cache_size = len(self._detail_cache)
        with self._detail_metrics_lock:
            detail_skipped = self._detail_skipped
            detail_reason_counts = dict(self._detail_reason_counts)
        return {
            "detail_requests": detail_requests,
            "detail_cache_hits": detail_cache_hits,
            "detail_skipped": detail_skipped,
            "detail_cache_size": cache_size,
            "detail_reason_counts": detail_reason_counts,
        }
