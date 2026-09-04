import contextlib
import json
import re
from typing import ClassVar
from urllib.parse import urljoin

from scrapers.extractors.price_extractor import PriceExtractor
from scrapers.extractors.stock_extractor import StockExtractor
from scrapers.factories.scraped_product_factory import ScrapedProductFactory
from scrapers.selectors import product_selectors


class ProductExtractor:
    """Extrae información de productos desde páginas WooCommerce."""

    SOURCE = "importacionesfacundo"
    BASE_URL = "https://stock.importacionesfacundo.com"
    _CODE_PATTERN = re.compile(r"^[A-Z0-9]{1,16}(?:-[A-Z0-9]+)*$", re.IGNORECASE)

    _IGNORED_COLOR_TAGS = (
        "select",
        "option",
        "script",
        "style",
        "noscript",
        "template",
    )
    _INVALID_COLOR_MARKERS: ClassVar[set[str]] = {
        "var acss",
        "sourceurl=",
        "sourceurl:",
        "javascript",
        "color_mode",
        "enable_client_color_preference",
    }

    def __init__(self):
        self.price_extractor = PriceExtractor()
        self.stock_extractor = StockExtractor()

    def extract(self, soup, url="", category=""):
        color_stock = self.extract_color_stock(soup)
        stock = self.stock_extractor.extract(soup)
        if color_stock:
            stock = sum(color_stock.values())

        price_sample = self.price_extractor.extract_sample(soup)
        return ScrapedProductFactory.create(
            source=self.SOURCE,
            url=url,
            code=self.extract_code(soup),
            name=self.extract_name(soup),
            category=category,
            description=self.extract_description(soup),
            stock=stock,
            price=self.extract_price(soup) or price_sample,
            price_sample=price_sample,
            price_hundred=self.price_extractor.extract_hundred(soup),
            price_thousand=self.price_extractor.extract_thousand(soup),
            color_stock=color_stock,
            image_url=self.extract_image(soup),
        )

    @classmethod
    def _normalize_code_candidate(cls, text: str) -> str:
        """Valida un código completo sin asumir un prefijo concreto."""
        candidate = str(text).strip().strip(".,:;()[]{}")
        if not cls._CODE_PATTERN.fullmatch(candidate):
            return ""
        if not any(char.isalpha() for char in candidate):
            return ""
        if not any(char.isdigit() for char in candidate):
            return ""
        return candidate.upper()

    @classmethod
    def _find_code_token(cls, text: str) -> str:
        """Busca un código dentro de texto explícitamente marcado como SKU."""
        for token in re.split(r"\s+", str(text).strip()):
            code = cls._normalize_code_candidate(token)
            if code:
                return code
        return ""

    def extract_code(self, soup):
        selectors = [
            "p.brxe-heading",
            "span.sku",
            "[sku]",
            "[data-sku]",
            ".sku",
        ]
        for selector in selectors:
            for element in soup.select(selector):
                text = (
                    element.get("sku")
                    or element.get("data-sku")
                    or element.get_text(" ", strip=True)
                )
                code = self._normalize_code_candidate(str(text))
                if code:
                    return code

        code_marker = re.compile(r"\b(?:c[oó]digo|sku|cod)\b", re.I)
        for text_node in soup.find_all(string=code_marker):
            parent = text_node.parent
            if parent is None:
                continue
            code = self._find_code_token(parent.get_text(" ", strip=True))
            if code:
                return code

            sibling = parent.find_next(string=True)
            if sibling is not None:
                code = self._find_code_token(str(sibling))
                if code:
                    return code

        return ""

    def extract_name(self, soup):
        selectors = ["h2.brxe-heading", "h1", product_selectors.PRODUCT_NAME]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(" ", strip=True)
        return ""

    def extract_description(self, soup):
        selectors = [
            ".text-content",
            ".x-tabs_panel-content",
            ".product-description",
            product_selectors.PRODUCT_DESCRIPTION,
            ".description",
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(" ", strip=True)
        return ""

    def extract_price(self, soup):
        selectors = [
            ".product-price",
            ".price",
            "span.price",
            ".woocommerce-Price-amount",
            "[class*='price']",
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(" ", strip=True)
                clean = (
                    text.replace("S/", "")
                    .replace("$", "")
                    .replace(",", "")
                    .strip()
                )
                try:
                    return float(clean)
                except ValueError:
                    continue
        return 0.0

    def extract_color_stock(self, soup) -> dict[str, int]:
        """Extrae exclusivamente el stock asociado a cada color visible."""
        color_stock: dict[str, int] = {}
        color_labels: dict[str, str] = {}
        add_color = self._build_color_adder(color_stock, color_labels)

        self._collect_color_labels(soup, color_labels)

        explicit_colors = self._extract_text_colors(soup)
        visible_stock = self._extract_visible_stock_values(soup)
        if explicit_colors:
            for color in explicit_colors:
                add_color(color)
            if len(explicit_colors) == len(visible_stock):
                for color, stock in zip(explicit_colors, visible_stock, strict=True):
                    add_color(color, stock)
                return color_stock
            if not visible_stock:
                return color_stock

        self._extract_select_color_stock(soup, add_color)
        self._extract_element_color_stock(soup, add_color)
        self._extract_variation_color_stock(soup, add_color, color_labels)
        self._apply_visible_color_stock(soup, color_stock)
        return color_stock

    @staticmethod
    def _build_color_adder(color_stock, color_labels):
        def add_color(name: str, stock: int | None = None) -> None:
            normalized = re.sub(r"\s+", " ", str(name)).strip(" .:-|")
            if not ProductExtractor._is_valid_color_name(normalized):
                return
            normalized = color_labels.get(normalized.casefold(), normalized)
            color_stock.setdefault(normalized, 0)
            if stock is not None:
                color_stock[normalized] = max(
                    color_stock.get(normalized, 0),
                    max(stock, 0),
                )

        return add_color

    @classmethod
    def _is_valid_color_name(cls, value: str) -> bool:
        folded = value.casefold()
        invalid = (
            not value
            or len(value) > 80
            or folded
            in {
                "color",
                "colour",
                "colores",
                "seleccionar color",
                "choose an option",
            }
            or any(marker in folded for marker in cls._INVALID_COLOR_MARKERS)
        )
        return not invalid
