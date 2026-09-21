import contextlib
import re
from typing import ClassVar
from urllib.parse import urljoin

from scrapers.extractors.code_utils import extract_code_from_soup, normalize_code
from scrapers.extractors.price_extractor import PriceExtractor
from scrapers.extractors.stock_extractor import StockExtractor
from scrapers.factories.scraped_product_factory import ScrapedProductFactory
from scrapers.selectors import product_selectors


class ProductExtractor:
    """Extrae información de productos desde páginas WooCommerce."""

    SOURCE = "importacionesfacundo"
    BASE_URL = "https://stock.importacionesfacundo.com"

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
        self._extracted_codes = {}

    def extract(self, soup, url="", category=""):
        text = soup.get_text(" ", strip=True)
        color_stock = self.extract_color_stock(soup, text=text)
        visible_stock = self._extract_visible_stock_values(soup, text=text)
        stock = self.stock_extractor.extract(soup, text=text)
        if color_stock:
            color_total = sum(color_stock.values())
            if color_total > 0 or len(color_stock) == len(visible_stock):
                stock = color_total
        code = self.extract_code(soup)
        self._extracted_codes[id(soup)] = code

        return ScrapedProductFactory.create(
            source=self.SOURCE,
            url=url,
            code=code,
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
        """Valida un código completo sin asumir un prefijo concreto."""
        return normalize_code(text)

    @classmethod
    def _find_code_token(cls, text: str) -> str:
        """Busca un código dentro de texto explícitamente marcado como SKU."""
        for token in re.split(r"\s+", str(text).strip()):
            code = cls._normalize_code_candidate(token)
            if code:
                return code
        return ""

    def extract_code(self, soup):
        return extract_code_from_soup(
            soup,
            fallback=ProductExtractor._extract_code_from_marked_text,
            extractor=self,
        )

    @classmethod
    def _extract_code_from_marked_text(cls, self, soup) -> str:
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

    def extract_color_stock(self, soup, text: str | None = None) -> dict[str, int]:
        """Extrae exclusivamente el stock asociado a cada color visible."""
        color_stock: dict[str, int] = {}
        color_labels: dict[str, str] = {}
        color_names: list[str] = []
        add_color = self._build_color_adder(
            color_stock,
            color_labels,
            color_names,
        )

        self._collect_color_labels(soup, color_labels)

        explicit_colors = self._extract_text_colors(soup)
        visible_stock = self._extract_visible_stock_values(soup, text=text)
        if explicit_colors and len(explicit_colors) == len(visible_stock):
            return {
                color: stock
                for color, stock in zip(
                    explicit_colors,
                    visible_stock,
                    strict=True,
                )
            }

        for color in explicit_colors:
            add_color(color)

        self._extract_select_color_stock(soup, add_color)
        self._extract_element_color_stock(soup, add_color)
        self._extract_variation_color_stock(soup, add_color, color_labels)

        if color_stock and len(color_stock) == len(color_names):
            return color_stock

        if not color_stock and color_names:
            return {color: 0 for color in color_names}

        if color_names and len(color_names) == len(visible_stock):
            return {
                color: stock
                for color, stock in zip(
                    color_names,
                    visible_stock,
                    strict=True,
                )
            }

        return {}

    @staticmethod
    def _build_color_adder(color_stock, color_labels, color_names):
        color_keys: set[str] = set()

        def add_color(name: str, stock: int | None = None) -> None:
            normalized = re.sub(r"\s+", " ", str(name)).strip(" .:-|")
            if not ProductExtractor._is_valid_color_name(normalized):
                return
            normalized = color_labels.get(normalized.casefold(), normalized)
            key = normalized.casefold()
            if key not in color_keys:
                color_keys.add(key)
                color_names.append(normalized)
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
        stop = (
            r"(?=\s+(?:stock\s+disponible|precio|presentaci[oó]n|"
            r"c[oó]digo|sku|categor[ií]as?)\b|[.;]|$)"
        )
        patterns = (
            re.compile(
                r"\b(?:\d+\s+)?colores?"
                r"(?:\s+(?:disponibles?|de\s+tinta))?"
                rf"\s*[:|\-]\s*(.+?){stop}",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:disponible|disponibles)\s+(?:en\s+)?"
                r"(?:los\s+)?colores?\s+[^.;]*?\bcomo\b\s*(.+?)"
                rf"{stop}",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:disponible|disponibles)\s+(?:en\s+)?"
                r"(?:los\s+)?colores?\s*[:|\-]?\s*(.+?)"
                rf"{stop}",
                flags=re.IGNORECASE,
            ),
            re.compile(
                rf"\bcolor\s*[:|\-]\s*(.+?){stop}",
                flags=re.IGNORECASE,
            ),
        )
        marker = re.compile(
            r"\b(?:\d+\s+)?colores?"
            r"(?:\s+(?:disponibles?|de\s+tinta))?"
            r"|\b(?:disponible|disponibles)\s+(?:en\s+)?"
            r"(?:los\s+)?colores?"
            r"|\bcolor\s*[:|\-]",
            re.IGNORECASE,
        )
        for element in soup.find_all(string=marker):
            element_text = str(element).strip()
            for pattern in patterns:
                match = pattern.search(element_text)
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
        normalized = re.sub(r"\s*\([^)]*\)\s*$", "", normalized)
        casefolded = normalized.casefold()
        if " como " in casefolded:
            normalized = normalized[casefolded.rfind(" como ") + len(" como ") :]
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
    def _extract_visible_stock_values(soup, text: str | None = None) -> list[int]:
        extracted_text = text if isinstance(text, str) else soup.get_text(" ", strip=True)
        match = re.search(
            r"stock\s+disponible\s*((?:\d[\d,.]*\s*)+)",
            extracted_text,
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

    def _extract_variation_colors(self, value, add_color, color_labels, inherited_stock=None) -> None:
        if isinstance(value, dict):
            stock = self._variation_stock(value)
            if stock is None:
                stock = inherited_stock
            color_name = self._variation_color(value, color_labels)
            if color_name:
                add_color(color_name, stock)
            for item in value.values():
                self._extract_variation_colors(item, add_color, color_labels, stock)
            return
        if isinstance(value, list):
            for item in value:
                self._extract_variation_colors(item, add_color, color_labels, inherited_stock)

    @staticmethod
    def _variation_stock(value: dict) -> int | None:
        stock_keys = {"max_qty", "max_quantity", "stock", "quantity", "stock_quantity"}
        for key, item in value.items():
            if str(key).casefold() not in stock_keys:
                continue
            with contextlib.suppress(TypeError, ValueError):
                return int(item)
        return None

    @staticmethod
    def _variation_color(value: dict, color_labels: dict[str, str] | None = None) -> str:
        for key, item in value.items():
            key_text = str(key).casefold()
            if isinstance(item, str) and ("color" in key_text or "colour" in key_text):
                if color_labels:
                    return color_labels.get(item.casefold(), item)
                return item
            if isinstance(item, dict):
                nested = ProductExtractor._variation_color(item, color_labels)
                if nested:
                    return nested
        return ""

    @staticmethod
    def _json_payloads(raw: str):
        try:
            import json
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        return [parsed]

    @staticmethod
    def _stock_from_tag(element) -> int | None:
        for key in ("data-stock", "data-quantity", "data-max-qty", "data-max_quantity"):
            value = element.get(key)
            if value is not None:
                try:
                    return int(float(str(value).strip()))
                except ValueError:
                    pass
        return None

    def extract_image(self, soup):
        code = self._extracted_codes.pop(id(soup), None)
        if code is None:
            code = self.extract_code(soup)
        candidates = []
        for img in soup.find_all("img"):
            url = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
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
        if not url.startswith(("http://", "https://")):
            return urljoin(self.BASE_URL + "/", url)
        return url
