import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from models.scraping.scraped_product import ScrapedProduct

logger = logging.getLogger("FCM")


class CategoryProductScraper:
    """Scraper de tarjetas y enriquecimiento selectivo de productos."""

    def __init__(self, browser, category_scraper, product_extractor, detail_cache=None):
        self.browser = browser
        self.category_scraper = category_scraper
        self.product_extractor = product_extractor
        self.detail_cache = detail_cache
        self._detail_metrics_lock = threading.Lock()
        self.reset_detail_metrics()

    def reset_detail_metrics(self):
        self._detail_requests = 0
        self._detail_cache_hits = 0
        self._detail_skipped = 0
        self._detail_reason_counts = {}

    def get_detail_metrics(self):
        with self._detail_metrics_lock:
            return {
                "detail_requests": self._detail_requests,
                "detail_cache_hits": self._detail_cache_hits,
                "detail_skipped": self._detail_skipped,
                "detail_cache_size": self._cache_size(),
                "detail_reason_counts": dict(self._detail_reason_counts),
            }

    def collect_category(self, category):
        """Obtiene solamente las tarjetas de una categoría."""
        html = self.category_scraper.get_category_html(category.url)
        return self.product_extractor.extract_collection(html, category.name)

    def enrich_category_products(self, collected, category_name):
        """Enriquece únicamente los productos que realmente necesitan detalle."""
        products = list(collected)
        candidates = []
        for product in products:
            reason = self._detail_reason(product)
            if reason is None:
                self._record_skip()
                continue
            self._record_reason(reason)
            candidates.append(product)

        if not candidates:
            return products

        max_workers = min(20, len(candidates))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    self._enrich_one,
                    product,
                    category_name,
                )
                for product in candidates
            ]
            enriched = [future.result() for future in futures]

        enriched_by_code = {
            self._cache_key(product): product for product in enriched
        }
        return [
            enriched_by_code.get(self._cache_key(product), product)
            for product in products
        ]

    def _detail_reason(self, product):
        """Devuelve la razón real por la que una tarjeta requiere detalle.

        Los precios ausentes por sí solos no fuerzan una solicitud de detalle:
        el detalle solo se solicita cuando faltan datos estructurales que no
        pueden recuperarse de forma segura desde la tarjeta.
        """
        code = self._value(product, "code")
        name = self._value(product, "name")
        image_url = self._value(product, "image_url")
        description = self._value(product, "description")
        stock = self._value(product, "stock")

        if not code:
            return "missing_code"
        if not name:
            return "missing_name"
        if not image_url:
            return "missing_image"
        if not description:
            return "missing_description"

        # Stock múltiple por color/variación es información de detalle sensible;
        # conservar la consulta cuando la tarjeta no expone una representación
        # inequívoca de todas las variantes.
        stock_values = self._stock_values(product)
        if stock_values and len(stock_values) > 1:
            return "multiple_stock"
        if stock is None:
            return "missing_stock"

        return None

    def _enrich_one(self, product, category_name):
        key = self._cache_key(product)
        if key and self.detail_cache is not None:
            cached = self.detail_cache.get(key)
            if cached is not None:
                with self._detail_metrics_lock:
                    self._detail_cache_hits += 1
                return self._merge(product, cached)

        url = self._value(product, "url") or self._value(product, "product_url")
        if not url:
            return product

        with self._detail_metrics_lock:
            self._detail_requests += 1

        html = self.browser.get(url)
        if not html:
            return product

        detail = self.product_extractor.extract_detail(
            html,
            url=url,
            category=category_name,
        )
        if self.detail_cache is not None and key:
            self.detail_cache.set(key, detail)
        return self._merge(product, detail)

    def _merge(self, base, detail):
        if detail is None:
            return base
        if hasattr(base, "__dataclass_fields__"):
            values = {
                field: getattr(base, field)
                for field in base.__dataclass_fields__
            }
            for field in values:
                detail_value = getattr(detail, field, None)
                if detail_value not in (None, "", [], {}):
                    values[field] = detail_value
            return type(base)(**values)

        for field in getattr(detail, "__dict__", {}):
            value = getattr(detail, field)
            if value not in (None, "", [], {}):
                setattr(base, field, value)
        return base

    @staticmethod
    def _value(product, name):
        value = getattr(product, name, None)
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _stock_values(product):
        values = getattr(product, "stock_by_color", None)
        if values:
            return values
        values = getattr(product, "colors_stock", None)
        if values:
            return values
        return []

    def _cache_key(self, product):
        return self._value(product, "code") or self._value(product, "url")

    def _cache_size(self):
        cache = self.detail_cache
        if cache is None:
            return 0
        try:
            return len(cache)
        except TypeError:
            return 0

    def _record_skip(self):
        with self._detail_metrics_lock:
            self._detail_skipped += 1

    def _record_reason(self, reason):
        with self._detail_metrics_lock:
            self._detail_reason_counts[reason] = (
                self._detail_reason_counts.get(reason, 0) + 1
            )
