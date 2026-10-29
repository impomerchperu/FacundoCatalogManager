import re

from bs4 import BeautifulSoup

from models.scraping.detail_description_policy import (
    has_technical_detail,
    is_valid_detail_content,
    normalize_detail_text,
)
from models.scraping.scraped_product import ScrapedProduct
from scrapers.extractors.code_utils import normalize_code_token
from scrapers.extractors.price_extractor import PriceExtractor
from scrapers.extractors.product_image_extractor import ProductImageExtractor
from scrapers.extractors.variant_color_stock_extractor import (
    extract_variant_color_stock,
)


class CategoryProductExtractor:
    """Extrae productos desde tarjetas y filas de tabla de categoría."""

    SOURCE = "importacionesfacundo"
    _EXPLICIT_CODE_MARKER_PATTERN = re.compile(
        r"\b(?:sku|c[oó]digo|cod)\s*[:#-]\s*([A-Z0-9][A-Z0-9._/-]{0,31})",
        re.IGNORECASE,
    )
    _NON_DETAIL_FIELD_PATTERN = re.compile(
        r"(?:"
        r"\bstock\s+disponible\s*:?\s*\d[\d,.]*|"
        r"(?:^|[.!?;]\s+)precio\s+(?:muestra|ciento|millar)"
        r"\s*(?::\s*(?:s/\s*)?|s/\s*|-\s*)(?:\d|consultar|disponible)|"
        r"(?:^|[.!?]\s+)(?:sku\s*[:\-]\s*[A-Z0-9-]+|"
        r"c[oó]digo\s*[:\-]\s*[A-Z0-9-]+))",
        re.IGNORECASE,
    )
    _EXCLUDED_DETAIL_TAB_IDS = frozenset({
        "tab-description",
        "tab-additional_information",
        "tab-additional-information",
        "tab-reviews",
    })
    _EXCLUDED_DETAIL_TAB_CLASSES = frozenset({
        "woocommerce-Tabs-panel--description",
        "woocommerce-Tabs-panel--additional_information",
        "woocommerce-Tabs-panel--reviews",
        "x-tabs_panel-content",
    })
    _NON_DETAIL_SECTION_PREFIX_PATTERN = re.compile(
        r"^\s*(?:informaci[oó]n adicional|reseñas?|valoraciones)\s*[:\-]",
        re.IGNORECASE,
    )

    def __init__(self):
        self.price_extractor = PriceExtractor()

    def extract(self, card, url="", category=""):
        color_stock = self._color_stock(card)
        stock_values = self._stock_values(card)
        total_stock = sum(stock_values) if stock_values else self._stock(card)
        if color_stock and len(color_stock) == len(stock_values):
            total_stock = sum(color_stock.values())

        price_sample = self.price_extractor.extract_sample(card)
        code = self._code(card)
        name = self._name(card)
        image_candidates = ProductImageExtractor.extract_candidates(
            card,
            code=code,
            name=name,
            base_url=ProductImageExtractor.BASE_URL,
        )
        result = ScrapedProduct(
            source=self.SOURCE,
            url=url or self._url(card),
            code=code,
            name=name,
            category=category,
            description=self._description(card),
            stock=total_stock,
            price=price_sample,
            price_sample=price_sample,
            price_hundred=self.price_extractor.extract_hundred(card),
            price_thousand=self.price_extractor.extract_thousand(card),
            color_stock=color_stock,
            image_url=image_candidates[0]["url"] if image_candidates else "",
        )
        result.image_candidates = image_candidates
        return result

    def _url(self, soup):
        element = soup.select_one('a[href*="/producto/"]')
        return element.get("href", "") if element else ""

    @classmethod
    def _normalize_code(
        cls,
        text: str,
        *,
        allow_alpha_only: bool = False,
    ) -> str:
        return normalize_code_token(text, allow_alpha_only=allow_alpha_only)

    @classmethod
    def _code(cls, soup):
        """Extrae el código aunque cambie la plantilla visual del SKU."""
        selectors = (
            "p.brxe-a26f34",
            "span.sku",
            ".sku",
            "[sku]",
            "[data-sku]",
            "p[class*='sku']",
            "span[class*='sku']",
        )
        for selector in selectors:
            for element in soup.select(selector):
                text = (
                    element.get("sku")
                    or element.get("data-sku")
                    or element.get_text(" ", strip=True)
                )
                code = cls._normalize_code(
                    text,
                    allow_alpha_only=selector in {
                        "p.brxe-a26f34",
                        "span.sku",
                        ".sku",
                        "p[class*='sku']",
                        "span[class*='sku']",
                        "[sku]",
                        "[data-sku]",
                    },
                )
                if code:
                    return code

        marked_code = cls._EXPLICIT_CODE_MARKER_PATTERN.search(
            soup.get_text(" ", strip=True)
        )
        if marked_code is not None:
            code = cls._normalize_code(
                marked_code.group(1),
                allow_alpha_only=True,
            )
            if code:
                return code

        name_element = soup.select_one("h2.brxe-f31760, h2.brxe-heading, h2, h3")
        for text_node in soup.find_all(string=True):
            if name_element is not None and text_node is name_element.string:
                break
            code = cls._normalize_code(text_node)
            if code:
                return code
        return ""

    def _name(self, soup):
        """Extrae el título real antes de los encabezados de presentación."""
        selectors = (
            "h2.brxe-f31760",
            "h2.brxe-heading",
            "h2",
        )
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text(" ", strip=True)
                if name:
                    return name

        element = soup.select_one("h3.brxe-heading, h3")
        return element.get_text(" ", strip=True) if element else ""

    @classmethod
    def _is_excluded_detail_block(cls, element) -> bool:
        """Exclude tab panels and their nested content from category summaries."""
        node = element
        excluded_widget_classes = {
            "wc-tabs",
            "wc-tabs-wrapper",
            "woocommerce-tabs",
            "tabs-content",
            "tab-content",
            "brxe-tabs-nested",
            "brxe-tabs-content",
            "variations",
            "variations_form",
            "variaciones-producto",
            "variable-items-wrapper",
            "variable-item",
            "woocommerce-variation",
            "content-precio",
            "product-price",
            "price",
            "stock",
            "product_meta",
            "woocommerce-product-meta",
            "woocommerce-product-gallery",
            "woocommerce-breadcrumb",
            "cart",
        }
        while node is not None and getattr(node, "attrs", None) is not None:
            node_id = str(node.get("id", "") or "").strip().casefold()
            if node_id in cls._EXCLUDED_DETAIL_TAB_IDS or node_id.startswith(
                ("tab-", "tab_")
            ):
                return True

            role = str(node.get("role", "") or "").strip().casefold()
            if role in {"tab", "tablist", "tabpanel"}:
                return True

            if str(getattr(node, "name", "") or "").casefold() == "form":
                form_classes = {
                    str(value).strip().casefold()
                    for value in (node.get("class", []) or [])
                }
                if form_classes & {"variations_form", "cart"}:
                    return True

            aria_labelled_by = str(node.get("aria-labelledby", "") or "").casefold()
            if any(
                token in aria_labelled_by
                for token in (
                    "description",
                    "additional_information",
                    "additional-information",
                    "reviews",
                    "valoraciones",
                )
            ):
                return True

            classes = {
                str(value).strip().casefold()
                for value in (node.get("class", []) or [])
            }
            if classes & (
                cls._EXCLUDED_DETAIL_TAB_CLASSES | excluded_widget_classes
            ):
                return True
            if any(
                "tabs_panel-content" in class_name
                or class_name.startswith("woocommerce-tabs-panel--")
                for class_name in classes
            ):
                return True

            node = getattr(node, "parent", None)
        return False

    @staticmethod
    def _detail_text_from_element(element) -> str:
        """Preserva límites HTML para distinguir la descripción del resto."""
        boundary = "__FACUNDO_DETAIL_BOUNDARY__"
        markup = str(element)
        markup = re.sub(
            r"<br\b[^>]*>",
            boundary,
            markup,
            flags=re.IGNORECASE,
        )
        markup = re.sub(
            r"<(?:li|p|div|h[1-6])\b[^>]*>",
            boundary,
            markup,
            flags=re.IGNORECASE,
        )
        markup = re.sub(
            r"</(?:li|p|div|h[1-6])\s*>",
            boundary,
            markup,
            flags=re.IGNORECASE,
        )
        text = BeautifulSoup(markup, "lxml").get_text(" ", strip=True)
        return text.replace(boundary, " ␞ ")

    @classmethod
    def _description_candidate(cls, element) -> str:
        if cls._is_excluded_detail_block(element):
            return ""

        text = normalize_detail_text(cls._detail_text_from_element(element))
        if not text or cls._NON_DETAIL_SECTION_PREFIX_PATTERN.match(text):
            return ""

        # Remove stock, price and SKU fragments before deciding whether the text
        # belongs to Detail; these fields must never become part of its value.
        field_boundary = cls._NON_DETAIL_FIELD_PATTERN.search(text)
        if field_boundary is not None:
            text = text[: field_boundary.start()].strip(" .;:-")
        if not text:
            return ""

        technical = has_technical_detail(text)
        if is_valid_detail_content(text):
            # A short generic sentence in a card is not enough to establish
            # that it is the product's Detail field. Long marketing copy such
            # as HL-3000 remains valid because it is the actual field content.
            if not technical and len(text) < 35:
                return ""
            return text

        # Preserve a visibly truncated technical card value as the source of
        # truth if the individual page has no usable Detail. The collection
        # scraper can still request the page, but must not lose the card value
        # merely because the excerpt ends with an ellipsis.
        if technical and re.search(r"(?:\.{2,}|…)$", text):
            return text
        return ""

    @classmethod
    def _collect_description_candidates(cls, elements):
        candidates = []
        seen: set[str] = set()
        for element in elements:
            text = cls._description_candidate(element)
            identity = text.casefold()
            if not text or identity in seen:
                continue
            seen.add(identity)
            candidates.append(text)
        return candidates

    def _description(self, soup):
        # Only non-excluded .text-content blocks establish the authoritative
        # Detail field. A text-content selector inside a tab panel must not
        # suppress the visible Detail fields elsewhere in the category card.
        authoritative_elements = [
            element
            for element in soup.select(".text-content")
            if not self._is_excluded_detail_block(element)
        ]
        candidates = self._collect_description_candidates(authoritative_elements)
        if authoritative_elements and not candidates:
            return ""
        if not candidates:
            fallback_selectors = (
                ".brxe-text",
                ".brxe-text-basic",
                "ul li",
                "ol li",
            )
            candidates = self._collect_description_candidates(
                soup.select(", ".join(fallback_selectors))
            )

        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]
        prefix = ". ".join(
            candidate.rstrip(" .;")
            for candidate in candidates[:-1]
        )
        return f"{prefix}. {candidates[-1].lstrip()}"

    def _stock(self, soup):
        return sum(self._stock_values(soup))

    def _stock_values(self, soup) -> list[int]:
        """Extrae los valores de stock visibles en la tarjeta."""
        values: list[int] = []
        for value in soup.select(".variaciones-producto p"):
            text = value.get_text(" ", strip=True)
            if text.isdigit():
                values.append(int(text))
                continue

            match = re.match(r"^.+?\s*[:\-]\s*(\d[\d,.]*)\s*$", text)
            if match:
                try:
                    values.append(int(float(match.group(1).replace(",", ""))))
                except ValueError:
                    continue

        if values:
            return values

        text = soup.get_text(" ", strip=True)
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

    def _color_stock(self, soup) -> dict[str, int]:
        variant_color_stock = extract_variant_color_stock(soup)
        if variant_color_stock:
            return variant_color_stock

        color_stock: dict[str, int] = {}
        color_candidates: list[str] = []
        color_keys: set[str] = set()
        direct_stock_found = False

        def add_color(name: str, stock: int | None = None) -> None:
            nonlocal direct_stock_found
            value = re.sub(r"\s+", " ", str(name)).strip(" :-.")
            if not value or value.casefold() in {
                "color",
                "colour",
                "colores",
                "seleccionar color",
                "sin color",
            }:
                return

            key = value.casefold()
            if key not in color_keys:
                color_keys.add(key)
                color_candidates.append(value)

            if stock is not None:
                direct_stock_found = True
                color_stock[value] = max(
                    color_stock.get(value, 0),
                    max(stock, 0),
                )

        variation = soup.select_one(".variaciones-producto")
        if variation:
            for element in variation.select(
                "[data-color], [data-value], [title], .color, "
                ".color-name, .swatch",
            ):
                name = (
                    element.get("data-color")
                    or element.get("data-value")
                    or element.get("title")
                    or element.get_text(" ", strip=True)
                )
                add_color(name, self._stock_attribute(element))

            for paragraph in variation.select("p"):
                text = re.sub(
                    r"\s+",
                    " ",
                    paragraph.get_text(" ", strip=True),
                )
                match = re.match(r"^(.+?)\s*[:\-]\s*(\d+)\s*$", text)
                if match:
                    add_color(match.group(1), int(match.group(2)))

        self._extract_labeled_colors(soup, add_color)

        stock_values = self._stock_values(soup)
        if direct_stock_found and len(color_stock) == len(stock_values):
            return color_stock

        return {}

    @staticmethod
    def _extract_labeled_colors(soup, add_color) -> None:
        """Extrae colores declarados en la descripción de la tarjeta."""
        patterns = (
            re.compile(
                r"\b(?:\d+\s+)?colores?(?:\s+(?:disponibles?|de\s+tinta))?"
                r"\s*[:|\-]\s*(.+?)"
                r"(?=\s+(?:stock\s+disponible|precio|presentaci[oó]n|"
                r"c[oó]digo|sku|categor[ií]as?)\b|[.;]|$)",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:disponible|disponibles)\s+(?:en\s+)?"
                r"(?:los\s+)?colores?\s+[^.;]*?\bcomo\b\s*(.+?)"
                r"(?=\s+(?:stock\s+disponible|precio|presentaci[oó]n|"
                r"c[oó]digo|sku|categor[ií]as?)\b|[.;]|$)",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:disponible|disponibles)\s+(?:en\s+)?"
                r"(?:los\s+)?colores?\s*[:|\-]?\s*(.+?)"
                r"(?=\s+(?:stock\s+disponible|precio|presentaci[oó]n|"
                r"c[oó]digo|sku|categor[ií]as?)\b|[.;]|$)",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"\bcolor\s*[:|\-]\s*(.+?)"
                r"(?=\s+(?:stock\s+disponible|precio|presentaci[oó]n|"
                r"c[oó]digo|sku|categor[ií]as?)\b|[.;]|$)",
                flags=re.IGNORECASE,
            ),
        )

        for element in soup.find_all(string=True):
            text = re.sub(r"\s+", " ", str(element)).strip()
            if not text:
                continue
            match = next(
                (
                    pattern.search(text)
                    for pattern in patterns
                    if pattern.search(text)
                ),
                None,
            )
            if match is None:
                continue

            normalized = match.group(1).strip(" .|-")
            normalized = re.sub(r"\s*\([^)]*\)\s*$", "", normalized)
            casefolded = normalized.casefold()
            if " como " in casefolded:
                normalized = normalized[casefolded.rfind(" como ") + len(" como "):]
            normalized = re.sub(r"\s+(?:y|e)\s+", ", ", normalized)
            for item in normalized.split(","):
                add_color(item)

    @staticmethod
    def _stock_attribute(element) -> int | None:
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

    def _image(self, soup):
        images = soup.select('a[href*="/producto/"] img')
        for image in images:
            url = image.get("data-src") or image.get("src") or ""
            if not url or "data:image" in url:
                continue
            if "Proximo" in url or "Logo" in url:
                continue
            return self._normalize_image_url(url)
        return ""

    @staticmethod
    def _normalize_image_url(url):
        for item in (
            "-150x150",
            "-300x300",
            "-600x600",
            "-768x768",
            "-1024x1024",
        ):
            url = url.replace(item, "")
        return url
