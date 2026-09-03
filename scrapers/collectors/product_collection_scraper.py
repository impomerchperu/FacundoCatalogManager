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
    _REQUIRED_DETAIL_FIELDS = ("code", "name", "description", "image_url")

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
        self._page_metrics: dict[str, dict[str, Any]] = {}
        self._page_metrics_lock = Lock()
        self._detail_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._detail_fetch_executor = ThreadPoolExecutor(max_workers=self.max_workers)

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
            expected_count = category.expected_count
        else:
            category_url = category
            category_name = ""
            expected_count = 0

        products: list[tuple[Any, str, Any]] = []
        seen: set[str] = set()
        try:
            pages = self.category_scraper.get_category_pages(
                category_url,
                expected_count=expected_count,
            )
        except TypeError as exc:
            if "expected_count" not in str(exc):
                raise
            pages = self.category_scraper.get_category_pages(category_url)

        page_metrics: list[dict[str, Any]] = []
        for page_number, page in enumerate(pages, start=1):
            html = self.category_scraper.get_html(page)
            if not html:
                page_metrics.append(
                    self._build_page_metric(
                        page_number=page_number,
                        page_url=page,
                        html_available=False,
                        card_count=0,
                        unique_product_count=0,
                    )
                )
                continue
            parser = getattr(self.category_scraper, "_parse", None)
            soup = (
                parser(html)
                if callable(parser)
                else BeautifulSoup(html, "html.parser")
            )
            cards = self._extract_cards(soup)
            page_seen_before = len(seen)
            for card in cards:
                product = self._extract_product_from_card(
                    card,
                    url="",
                    category=category_name,
                )
                product_url = self._card_detail_url(card, page, product)
                if product_url:
                    product.url = product_url
                identity = self._product_identity(
                    product,
                    product_url,
                    page,
                    card,
                )
                if identity in seen:
                    continue
                seen.add(identity)
                products.append((card, page, product))
            page_metrics.append(
                self._build_page_metric(
                    page_number=page_number,
                    page_url=page,
                    html_available=True,
                    card_count=len(cards),
                    unique_product_count=len(seen) - page_seen_before,
                )
            )
        self._store_page_metrics(
            category_url=category_url,
            category_name=category_name,
            expected_count=expected_count,
            pages=page_metrics,
            unique_products=len(products),
        )
        return products

    @staticmethod
    def _build_page_metric(
        *,
        page_number: int,
        page_url: str,
        html_available: bool,
        card_count: int,
        unique_product_count: int,
    ) -> dict[str, Any]:
        return {
            "page": page_number,
            "url": page_url,
            "html_available": html_available,
            "cards": card_count,
            "unique_products": unique_product_count,
        }

    def _store_page_metrics(
        self,
        *,
        category_url: str,
        category_name: str,
        expected_count: int,
        pages: list[dict[str, Any]],
        unique_products: int,
    ) -> None:
        with self._page_metrics_lock:
            self._page_metrics[category_url] = {
                "category": category_name,
                "expected_count": int(expected_count or 0),
                "pages_expected": (
                    (int(expected_count) + 24) // 25
                    if int(expected_count or 0) > 0
                    else len(pages)
                ),
                "pages_requested": len(pages),
                "pages_loaded": sum(
                    1 for page in pages if page["html_available"]
                ),
                "cards_found": sum(page["cards"] for page in pages),
                "unique_products": unique_products,
                "pages": pages,
            }

    def reset_page_metrics(self) -> None:
        with self._page_metrics_lock:
            self._page_metrics.clear()

    def get_page_metrics(self) -> dict[str, dict[str, Any]]:
        with self._page_metrics_lock:
            return {
                category_url: {
                    **metrics,
                    "pages": [dict(page) for page in metrics["pages"]],
                }
                for category_url, metrics in self._page_metrics.items()
            }

    @staticmethod
    def _product_identity(
        product: Any,
        product_url: str,
        page_url: str,
        card: Any,
    ) -> str:
        """Usa el código real como identidad y URL/tarjeta solo como respaldo."""
        code = str(getattr(product, "code", "")).strip().casefold()
        if code:
            return f"code:{code}"
        if product_url:
            return f"url:{product_url.casefold()}"
        try:
            card_text = " ".join(card.stripped_strings).strip().casefold()
        except AttributeError:
            card_text = ""
        return f"page:{page_url.casefold()}|card:{card_text}"

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
        with self._detail_cache_lock:
            preexisting_cache_keys = set(self._detail_cache)
        counted_cache_hits: set[str] = set()
        futures: list[tuple[int, Future[Any]]] = []
        for index, (card, page_url, product) in enumerate(products):
            skip_reason = self._detail_skip_reason(card, product)
            if skip_reason is not None:
                product.url = self._card_detail_url(card, page_url, product)
                with self._detail_metrics_lock:
                    self._detail_skipped += 1
                    self._record_detail_reason(f"skipped_{skip_reason}")
                continue

            detail_url = self._card_detail_url(card, page_url, product)
            detail_key = self._detail_cache_key(card, product, detail_url)
            if (
                detail_key in preexisting_cache_keys
                and detail_key not in counted_cache_hits
            ):
                counted_cache_hits.add(detail_key)
                with self._detail_cache_lock:
                    self._detail_cache_hits += 1

            request_reason = self._detail_request_reason(card, product)
            with self._detail_metrics_lock:
                self._record_detail_reason(f"requested_{request_reason}")
                if request_reason == "missing_fields":
                    missing_fields = self._missing_detail_fields(product)
                    for field in missing_fields:
                        self._record_detail_reason(f"requested_missing_{field}")
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
        if cls._has_complete_card_color_stock(card, product):
            return "complete_color_stock"

        stock_values = cls._stock_values(card)
        if len(stock_values) != 1:
            return None

        if cls._missing_detail_fields(product):
            return None
        if cls._missing_price_fields(card, product):
            return None
        return "complete_single_stock"

    @classmethod
    def _detail_request_reason(cls, card: Any, product: Any) -> str:
        stock_values = cls._stock_values(card)
        if len(stock_values) != 1:
            return cls._stock_request_reason(card, stock_values)
        if cls._missing_detail_fields(product):
            return "missing_fields"
        if cls._missing_price_fields(card, product):
            return "missing_prices"
        return "other"

    @classmethod
    def _missing_detail_fields(cls, product: Any) -> tuple[str, ...]:
        return tuple(
            field
            for field in cls._REQUIRED_DETAIL_FIELDS
            if not str(getattr(product, field, "")).strip()
        )

    @staticmethod
    def _stock_request_reason(card: Any, stock_values: list[int]) -> str:
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
        card_text = " ".join(card.stripped_strings).casefold()
        return tuple(
            field
            for field in cls._PRICE_FIELDS
            if float(getattr(product, field, 0.0) or 0.0) <= 0
            and cls._PRICE_LABELS[field] in card_text
        )

    @classmethod
    def _can_skip_detail(cls, card: Any, product: Any) -> bool:
        return cls._detail_skip_reason(card, product) is not None

    def _record_detail_reason(self, reason: str) -> None:
        self._detail_reason_counts[reason] = (
            self._detail_reason_counts.get(reason, 0) + 1
        )

    @staticmethod
    def _has_complete_card_color_stock(card: Any, product: Any) -> bool:
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

    def _extract_product_from_card(
        self,
        card: Any,
        *,
        url: str,
        category: str,
    ) -> Any:
        if callable(self.product_extractor):
            return self.product_extractor(card, url=url, category=category)
        return self.product_extractor.extract(card, url=url, category=category)

    def _enrich_from_detail_page(  # noqa: PLR0912
        self,
        card: Any,
        page_url: str,
        product: Any,
        category_name: str,
    ) -> Any:
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

        product.url = detail_url

        for field in ("code", "name", "description", "image_url"):
            current = str(getattr(product, field, "") or "").strip()
            detail_value = getattr(detailed_product, field, "")
            if not current and str(detail_value or "").strip():
                setattr(product, field, detail_value)

        for field in self._PRICE_FIELDS:
            current = float(getattr(product, field, 0.0) or 0.0)
            detail_value = float(getattr(detailed_product, field, 0.0) or 0.0)
            if current <= 0 and detail_value > 0:
                setattr(product, field, detail_value)

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
            return product

        if not card_stock_values:
            detail_stock = int(getattr(detailed_product, "stock", 0) or 0)
            if getattr(product, "stock", 0) <= 0 and detail_stock > 0:
                product.stock = detail_stock

        return product

    @staticmethod
    def _detail_cache_key(card: Any, product: Any, detail_url: str) -> str:
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
            if future is None:
                self._detail_requests += 1
                future = self._detail_fetch_executor.submit(
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
        parser = getattr(self.category_scraper, "_parse", None)
        soup = (
            parser(html)
            if callable(parser)
            else BeautifulSoup(html, "html.parser")
        )
        return self.detail_extractor.extract(
            soup,
            url=detail_url,
            category=category_name,
        )

    @staticmethod
    def _stock_values(card: Any) -> list[int]:
        values: list[int] = []
        variation = card.select_one(".variaciones-producto")
        if variation is not None:
            for paragraph in variation.select("p"):
                text = paragraph.get_text(" ", strip=True)
                numbers = re.findall(r"\d[\d,.]*", text)
                if numbers:
                    try:
                        values.append(int(float(numbers[-1].replace(",", ""))))
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
        with self._detail_cache_lock:
            self._detail_cache.clear()
            self._detail_requests = 0
            self._detail_cache_hits = 0
        with self._detail_metrics_lock:
            self._detail_skipped = 0
            self._detail_reason_counts.clear()

    def get_detail_metrics(self) -> dict[str, Any]:
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
