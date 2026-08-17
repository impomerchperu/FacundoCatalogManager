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
    _CODE_PATTERN = re.compile(r"^[A-Z0-9]{1,16}(?:-[A-Z0-9]+)+$", re.IGNORECASE)

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

        return ScrapedProductFactory.create(
            source=self.SOURCE,
            url=url,
            code=self.extract_code(soup),
            name=self.extract_name(soup),
            category=category,
            description=self.extract_description(soup),
            stock=stock,
            price=self.extract_price(soup),
            price_sample=self.price_extractor.extract_sample(soup),
            price_hundred=self.price_extractor.extract_hundred(soup),
            price_thousand=self.price_extractor.extract_thousand(soup),
            color_stock=color_stock,
            image_url=self.extract_image(soup),
        )

    @classmethod
    def _normalize_code_candidate(cls, text: str) -> str:
        """Devuelve un código válido del sitio sin asumir el prefijo FB-."""
        for token in re.split(r"\s+", text.strip()):
            candidate = token.strip(".,:;()[]{}")
            if cls._CODE_PATTERN.fullmatch(candidate):
                return candidate.upper()
        return ""

    def extract_code(self, soup):
        selectors = [
            "p.brxe-heading",
            "span.sku",
            "[sku]",
            "[data-sku]",
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if not element:
                continue
            text = element.get("sku") or element.get("data-sku") or element.get_text(
                " ",
                strip=True,
            )
            code = self._normalize_code_candidate(str(text))
            if code:
                return code

        for text_node in soup.find_all(string=re.compile(r"\b(?:c[oó]digo|sku)\b", re.I)):
            parent = text_node.parent
            if parent is None:
                continue
            code = self._normalize_code_candidate(parent.get_text(" ", strip=True))
            if code:
                return code

            sibling = parent.find_next(string=True)
            if sibling is not None:
                code = self._normalize_code_candidate(str(sibling))
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
            or "," in value
            or any(marker in folded for marker in cls._INVALID_COLOR_MARKERS)
            or any(token in value for token in ("{", "}", ";", "//", "=>"))
            or re.fullmatch(r"[\d\s.,:+-]+", value) is not None
        )
        return not invalid

    @staticmethod
    def _extract_select_color_stock(soup, add_color) -> None:
        for select in soup.select("select"):
            select_name = " ".join(
                str(select.get(attribute, ""))
                for attribute in ("name", "id", "class")
            ).casefold()
            if "color" not in select_name and "colour" not in select_name:
                continue
            for option in select.select("option"):
                value = option.get("value", "")
                label = option.get_text(" ", strip=True) or str(value)
                add_color(label, ProductExtractor._stock_from_tag(option))

    @classmethod
    def _extract_element_color_stock(cls, soup, add_color) -> None:
        for element in soup.find_all(True):
            if element.name in cls._IGNORED_COLOR_TAGS:
                continue
            if element.find(cls._IGNORED_COLOR_TAGS):
                continue

            attributes = " ".join(
                str(element.get(attribute, ""))
                for attribute in ("class", "id", "name", "data-attribute_name")
            ).casefold()
            if "color" not in attributes and "colour" not in attributes:
                continue

            value = (
                element.get("data-value")
                or element.get("data-color")
                or element.get("title")
            )
            if value:
                add_color(str(value), cls._stock_from_tag(element))
                continue

            direct_text = " ".join(
                str(text).strip()
                for text in element.find_all(string=True, recursive=False)
                if str(text).strip()
            )
            if direct_text:
                add_color(direct_text, cls._stock_from_tag(element))

    def _extract_variation_color_stock(
        self,
        soup,
        add_color,
        color_labels,
    ) -> None:
        for element in soup.select("[data-product_variations]"):
            raw = element.get("data-product_variations")
            if not isinstance(raw, str) or not raw.strip():
                continue
            for payload in self._json_payloads(raw):
                self._extract_variation_colors(
                    payload,
                    add_color,
                    color_labels,
                )

        for script in soup.find_all("script"):
            raw = script.string or script.get_text()
            if not raw or "variation" not in raw.casefold():
                continue
            for payload in self._json_payloads(raw):
                self._extract_variation_colors(
                    payload,
                    add_color,
                    color_labels,
                )

    @staticmethod
    def _apply_visible_color_stock(soup, color_stock) -> None:
        visible_stock = ProductExtractor._extract_visible_stock_values(soup)
        color_names = list(color_stock)
        if len(visible_stock) != len(color_names) or not color_names:
            return
        for color, stock in zip(color_names, visible_stock, strict=True):
            color_stock[color] = stock

    @staticmethod
    def _collect_color_labels(soup, color_labels: dict[str, str]) -> None:
        for select in soup.select("select"):
            select_name = " ".join(
                str(select.get(attribute, ""))
                for attribute in ("name", "id", "class")
            ).casefold()
            if "color" not in select_name and "colour" not in select_name:
                continue
            for option in select.select("option"):
                value = str(option.get("value", "")).strip()
                label = option.get_text(" ", strip=True)
                if value and label:
                    color_labels[value.casefold()] = label

    @classmethod
    def _extract_text_colors(cls, soup) -> list[str]:
        """Extrae listas explícitas y enlaces bajo el encabezado 'Colores'."""
        pattern = re.compile(
            r"\bcolores?\s*[:|\-]\s*(.+?)(?="
            r"\s+(?:stock\s+disponible|precio|presentaci[oó]n|"
            r"c[oó]digo|sku|categor[ií]as?)\b|$)",
            flags=re.IGNORECASE,
        )
        marker = re.compile(r"\bcolores?\s*[:|\-]", re.IGNORECASE)
        for element in soup.find_all(string=marker):
            match = pattern.search(str(element).strip())
            if match is None:
                continue
            colors = cls._split_color_text(match.group(1))
            if colors:
                return colors

        heading = re.compile(r"^\s*colores?\s*:?\s*$", re.IGNORECASE)
        for text_node in soup.find_all(string=heading):
            parent = text_node.parent
            if parent is None:
                continue
            colors = [
                link.get_text(" ", strip=True)
                for link in parent.find_all("a")
                if cls._is_valid_color_name(link.get_text(" ", strip=True))
            ]
            if colors:
                return colors
        return []

    @staticmethod
    def _split_color_text(value: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", value).strip(" .|-")
        normalized = re.sub(r"\s+(?:y|e)\s+", ", ", normalized)
        colors: list[str] = []
        seen: set[str] = set()
        for item in normalized.split(","):
            color = item.strip(" .|-")
            key = color.casefold()
            if color and key not in seen:
                seen.add(key)
                colors.append(color)
        return colors

    @staticmethod
    def _extract_visible_stock_values(soup) -> list[int]:
        """Extrae la secuencia de existencias tras 'Stock Disponible'."""
        text = soup.get_text(" ", strip=True)
        match = re.search(
            r"stock\s+disponible\s*((?:\d[\d,.]*\s*)+)",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            return []

        values: list[int] = []
        for raw_value in re.findall(r"\d[\d,.]*", match.group(1)):
            try:
                values.append(int(float(raw_value.replace(",", ""))))
            except ValueError:
                continue
        return values

    def _extract_variation_colors(
        self,
        value,
        add_color,
        color_labels: dict[str, str] | None = None,
        inherited_stock: int | None = None,
    ) -> None:
        if isinstance(value, dict):
            stock = self._variation_stock(value)
            if stock is None:
                stock = inherited_stock
            color_name = self._variation_color(value, color_labels)
            if color_name:
                add_color(color_name, stock)
            for item in value.values():
                self._extract_variation_colors(
                    item,
                    add_color,
                    color_labels,
                    stock,
                )
            return
        if isinstance(value, list):
            for item in value:
                self._extract_variation_colors(
                    item,
                    add_color,
                    color_labels,
                    inherited_stock,
                )

    @staticmethod
    def _variation_stock(value: dict) -> int | None:
        stock_keys = {
            "max_qty",
            "max_quantity",
            "stock",
            "quantity",
            "stock_quantity",
        }
        for key, item in value.items():
            if str(key).casefold() not in stock_keys:
                continue
            with contextlib.suppress(TypeError, ValueError):
                return int(item)
        return None

    @staticmethod
    def _variation_color(
        value: dict,
        color_labels: dict[str, str] | None = None,
    ) -> str:
        for key, item in value.items():
            key_text = str(key).casefold()
            if isinstance(item, str) and (
                "color" in key_text or "colour" in key_text
            ):
                color_name = item
                if color_labels:
                    color_name = color_labels.get(
                        color_name.casefold(),
                        color_name,
                    )
                return color_name
            if isinstance(item, dict):
                nested = ProductExtractor._variation_color(item, color_labels)
                if nested:
                    return nested
        return ""

    @staticmethod
    def _json_payloads(raw: str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        else:
            return [parsed]

    @staticmethod
    def _stock_from_tag(element) -> int | None:
        for key in (
            "data-stock",
            "data-quantity",
            "data-max-qty",
            "data-max_quantity",
        ):
            value = element.get(key)
            if value is not None:
                try:
                    return int(float(str(value).strip()))
                except ValueError:
                    pass
        return None

    def extract_image(self, soup):
        code = self.extract_code(soup)
        candidates = []
        for img in soup.find_all("img"):
            url = (
                img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("src")
                or ""
            )
            if not url or url.startswith("data:image"):
                continue
            if "Logo" in url or "Proximo" in url:
                continue
            candidates.append(self._normalize_image_url(url))

        if not candidates:
            return ""
        if code:
            for url in candidates:
                if code.lower() in url.lower():
                    return url
        for url in candidates:
            if "/uploads/" in url:
                return url
        return candidates[0]

    def _normalize_image_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.BASE_URL, url)
        return url
