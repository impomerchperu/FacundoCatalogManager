import contextlib
import re
from typing import ClassVar

from bs4 import BeautifulSoup

from models.scraping.detail_description_policy import (
    has_multiple_technical_detail_fields,
    has_technical_detail,
    is_complete_detail,
    is_valid_detail_content,
    normalize_detail_text,
    remove_incomplete_trailing_dimension_field,
)
from scrapers.extractors.code_utils import extract_code_from_soup, normalize_code
from scrapers.extractors.price_extractor import PriceExtractor
from scrapers.extractors.product_image_extractor import ProductImageExtractor
from scrapers.extractors.stock_extractor import StockExtractor
from scrapers.extractors.variant_color_stock_extractor import (
    extract_variant_color_stock,
)
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
    # The visible product summary is authoritative for the Detail field.
    # Tab panels (Description, Additional Information and Reviews) are excluded.
    _DETAIL_SELECTORS_BY_PRIORITY: ClassVar[tuple[tuple[str, ...], ...]] = (
        (".woocommerce-product-details__short-description",),
    )
    # The live product template also exposes the technical summary in .text-content.
    # It is a lower-priority fallback and must contain multiple technical fields.
    _DETAIL_FALLBACK_SELECTORS: ClassVar[tuple[str, ...]] = (
        ".text-content",
        ".brxe-text",
        ".brxe-text-basic",
        "ul",
        "ol",
        "p",
    )
    _EXCLUDED_DETAIL_TAB_IDS: ClassVar[frozenset[str]] = frozenset({
        "tab-description",
        "tab-additional_information",
        "tab-additional-information",
        "tab-reviews",
    })
    _EXCLUDED_DETAIL_TAB_CLASSES: ClassVar[frozenset[str]] = frozenset({
        "woocommerce-Tabs-panel--description",
        "woocommerce-Tabs-panel--additional_information",
        "woocommerce-Tabs-panel--reviews",
        "x-tabs_panel-content",
    })
    _NON_DETAIL_SECTION_PREFIX_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^\s*(?:informaci[oó]n adicional|reseñas?|valoraciones)\s*[:\-]",
        re.IGNORECASE,
    )

    _SEMANTIC_DETAIL_RULES: ClassVar[tuple[tuple[str, re.Pattern[str]], ...]] = (
        (
            "Compatibilidad",
            re.compile(
                r"\bcompatible con\s+(.+?)(?=,\s*ofrece\b|\.\s+[A-ZÁÉÍÓÚÑ]|[!?]|$)",
                re.IGNORECASE,
            ),
        ),
        (
            "Incluye",
            re.compile(
                r"\bincluye\s+(.+?)(?=\.\s+[A-ZÁÉÍÓÚÑ]|[!?]|$)",
                re.IGNORECASE,
            ),
        ),
        (
            "Acceso",
            re.compile(r"\bacceso\s+desde\s+([^.!?]+)", re.IGNORECASE),
        ),
        (
            "Conectividad",
            re.compile(
                r"\bmediante\s+((?:wi-?fi|airprint|whatsapp|bluetooth)[^.!?]+)",
                re.IGNORECASE,
            ),
        ),
        (
            "Función",
            re.compile(
                r"\b(imprime fotos y regalos personalizados con facilidad|"
                r"imprime fotos[^.!?]+)",
                re.IGNORECASE,
            ),
        ),
        (
            "Funciones adicionales",
            re.compile(
                r"\b(exportaci[oó]n rápida,\s*carrusel personalizable y "
                r"funcionamiento sin conexi[oó]n)",
                re.IGNORECASE,
            ),
        ),
        (
            "Funciones adicionales",
            re.compile(
                r"\b(ofrece múltiples formatos de impresión y personalización)",
                re.IGNORECASE,
            ),
        ),
        (
            "Compatibilidad",
            re.compile(
                r"\b(máquinas de corte,\s*como las de la marca Cricut)",
                re.IGNORECASE,
            ),
        ),
        (
            "Función",
            re.compile(r"\b(crea perforaciones o piquetes[^.!?]*)", re.IGNORECASE),
        ),
        (
            "Uso recomendado",
            re.compile(
                r"\b(?:te\s+)?(permite cortar materiales más gruesos y resistentes[^.!?]*)",
                re.IGNORECASE,
            ),
        ),
        (
            "Uso recomendado",
            re.compile(
                r"\b(proyectos que requieren cortes profundos en materiales como[^.!?]*)",
                re.IGNORECASE,
            ),
        ),
        (
            "Materiales",
            re.compile(r"\bmateriales como\s+([^.!?]+)", re.IGNORECASE),
        ),
        (
            "Función",
            re.compile(
                r"\b(se ajusta automáticamente según el tipo de material que estés cortando)",
                re.IGNORECASE,
            ),
        ),
    )
    _SEMANTIC_EXCLUDED_TAB_IDS: ClassVar[frozenset[str]] = frozenset({
        "tab-description",
        "tab-additional_information",
        "tab-additional-information",
        "tab-reviews",
    })
    _SEMANTIC_EXCLUDED_TAB_CLASSES: ClassVar[frozenset[str]] = frozenset({
        "woocommerce-Tabs-panel--description",
        "woocommerce-Tabs-panel--additional_information",
        "woocommerce-Tabs-panel--reviews",
        "x-tabs_panel-content",
    })

    def __init__(self):
        self.price_extractor = PriceExtractor()
        self.stock_extractor = StockExtractor()
        self._extracted_codes = {}

    def extract(self, soup, url="", category=""):
        text = soup.get_text(" ", strip=True)
        color_stock = self.extract_color_stock(soup, text=text)
        stock = self.stock_extractor.extract(soup, text=text)
        if color_stock:
            color_total = sum(color_stock.values())
            if color_total > 0:
                stock = color_total
        code = self.extract_code(soup)
        self._extracted_codes[id(soup)] = code
        image_candidates = self.extract_image_candidates(
            soup,
            base_url=url or self.BASE_URL,
        )
        result = ScrapedProductFactory.create(
            source=self.SOURCE,
            url=url,
            code=code,
            name=self.extract_name(soup),
            category=category,
            description=self.extract_detail_text(soup),
            stock=stock,
            price=self.extract_price(soup),
            price_sample=self.price_extractor.extract_sample(soup),
            price_hundred=self.price_extractor.extract_hundred(soup),
            price_thousand=self.price_extractor.extract_thousand(soup),
            color_stock=color_stock,
            image_url=image_candidates[0]["url"] if image_candidates else "",
        )
        result.image_candidates = image_candidates
        self._extracted_codes.pop(id(soup), None)
        return result

    @classmethod
    def _normalize_code_candidate(
        cls,
        text: str,
        *,
        allow_alpha_only: bool = False,
    ) -> str:
        """Valida un código completo sin asumir un prefijo concreto."""
        return normalize_code(text, allow_alpha_only=allow_alpha_only)

    @classmethod
    def _find_code_token(
        cls,
        text: str,
        *,
        allow_alpha_only: bool = False,
    ) -> str:
        """Busca un código en texto con una etiqueta explícita de SKU/código."""
        for token in re.split(r"\s+", str(text).strip()):
            code = cls._normalize_code_candidate(
                token,
                allow_alpha_only=allow_alpha_only,
            )
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
                code = self._normalize_code_candidate(
                    str(text),
                    allow_alpha_only=selector in {
                        "p.brxe-heading",
                        "span.sku",
                        ".sku",
                        "[sku]",
                        "[data-sku]",
                    },
                )
                if code:
                    return code

        code_marker = re.compile(r"\b(?:c[oó]digo|sku|cod)\b", re.I)
        for text_node in soup.find_all(string=code_marker):
            parent = text_node.parent
            if parent is None:
                continue
            code = self._find_code_token(
                parent.get_text(" ", strip=True),
                allow_alpha_only=True,
            )
            if code:
                return code

            sibling = parent.find_next(string=True)
            if sibling is not None:
                code = self._find_code_token(
                    str(sibling),
                    allow_alpha_only=True,
                )
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

    @classmethod
    def _is_complete_description(cls, value: str) -> bool:
        """Compatibilidad histórica: valida que Detalle sea técnico y completo."""
        return has_technical_detail(value) and is_complete_detail(value)

    @classmethod
    def _is_excluded_detail_tab(cls, element) -> bool:
        """Exclude tab panels and tab-navigation containers from the summary."""
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
        """Preserva límites HTML entre viñetas y saltos sin separar etiquetas y valores."""
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
        # Source indentation/newlines inside one text node are not field
        # boundaries. Collapse whitespace per chunk while retaining markers
        # inserted between structural HTML elements.
        chunks = [
            re.sub(r"\s+", " ", chunk).strip()
            for chunk in text.split(boundary)
        ]
        return " ␞ ".join(chunks)

    def _validated_detail_candidate(
        self,
        element,
        *,
        require_multiple_fields: bool,
    ) -> str:
        if self._is_excluded_detail_tab(element):
            return ""

        text = normalize_detail_text(
            self._detail_text_from_element(element),
            preserve_boundaries=True,
        )
        if (
            not text
            or self._NON_DETAIL_SECTION_PREFIX_PATTERN.match(text)
            or not is_valid_detail_content(text)
        ):
            return ""

        if (
            require_multiple_fields
            and not has_technical_detail(text)
            and len(text) < 35
        ):
            return ""
        return text

    def _extract_labeled_detail_blocks(self, soup) -> str:
        """Combina campos etiquetados cuando el tema los separa entre bloques HTML."""
        container_selectors = (
            ".woocommerce-product-details__short-description",
            ".text-content",
            ".brxe-div",
            ".brxe-text",
            ".brxe-text-basic",
        )
        block_selector = "li, p, .brxe-text, .brxe-text-basic"

        for container_selector in container_selectors:
            for container in soup.select(container_selector):
                if self._is_excluded_detail_tab(container):
                    continue
                blocks = container.select(block_selector)
                if len(blocks) < 2:
                    continue

                details = []
                seen = set()
                for block in blocks:
                    if self._is_excluded_detail_tab(block):
                        continue
                    detail = self._validated_detail_candidate(
                        block,
                        require_multiple_fields=False,
                    )
                    if not detail:
                        continue
                    identity = normalize_detail_text(detail).casefold()
                    if identity in seen:
                        continue
                    seen.add(identity)
                    details.append(detail)

                if len(details) < 2:
                    continue
                combined = normalize_detail_text(
                    " ␞ ".join(details),
                    preserve_boundaries=True,
                )
                if (
                    has_multiple_technical_detail_fields(combined)
                    and has_technical_detail(combined)
                    and is_complete_detail(combined)
                ):
                    return combined
        return ""

    @classmethod
    def _is_excluded_semantic_source(cls, element) -> bool:
        return cls._is_excluded_detail_tab(element)

    def _extract_semantic_detail_fields(self, soup) -> str:
        """Turn explicit compatibility, contents, and tool-function facts into labels."""
        source_selectors = (
            ".woocommerce-product-details__short-description",
            ".text-content",
            ".brxe-text",
            ".brxe-text-basic",
        )
        fields: list[str] = []
        seen: set[str] = set()

        for selector in source_selectors:
            for element in soup.select(selector):
                if self._is_excluded_semantic_source(element):
                    continue
                source_text = re.sub(
                    r"\s+",
                    " ",
                    element.get_text(" ", strip=True),
                )
                if not source_text:
                    continue

                for label, pattern in self._SEMANTIC_DETAIL_RULES:
                    for match in pattern.finditer(source_text):
                        value = re.sub(r"\s+", " ", match.group(1)).strip(
                            " \t\r\n.;,:"
                        )
                        if not value:
                            continue
                        if label == "Funciones adicionales":
                            value = re.sub(
                                r"^ofrece\s+",
                                "",
                                value,
                                flags=re.IGNORECASE,
                            )
                        if not value:
                            continue
                        value = value[0].upper() + value[1:]
                        field = f"{label}: {value}"
                        identity = normalize_detail_text(field).casefold()
                        if identity in seen:
                            continue
                        seen.add(identity)
                        fields.append(field)

        if not fields:
            return ""

        detail = normalize_detail_text(
            " ␞ ".join(fields),
            preserve_boundaries=True,
        )
        if has_technical_detail(detail) and is_complete_detail(detail):
            return detail
        return ""

    def extract_authoritative_detail_text(
        self,
        soup,
        *,
        preserve_boundaries: bool = False,
    ) -> tuple[bool, str]:
        """Return whether the authoritative Detail field was found and its value."""
        product_block = soup.select_one("#brxe-jhzpri")
        if product_block is not None and not self._is_excluded_detail_tab(product_block):
            elements = soup.select(
                "#brxe-jhzpri > ul > li, #brxe-jhzpri > p"
            )
            elements = [
                element
                for element in elements
                if not self._is_excluded_detail_tab(element)
            ]
            if elements:
                # The selected page field is authoritative as a whole. Do not
                # discard individual paragraphs merely because a label is not
                # in our technical-field vocabulary (e.g. Piezas, Forma,
                # Micrones, or supplier-specific attributes).
                field_text = " ␞ ".join(
                    self._detail_text_from_element(element)
                    for element in elements
                )
                return True, remove_incomplete_trailing_dimension_field(
                    normalize_detail_text(
                        field_text,
                        preserve_boundaries=preserve_boundaries,
                    )
                )

        summaries = [
            element
            for element in soup.select(
                ".woocommerce-product-details__short-description"
            )
            if not self._is_excluded_detail_tab(element)
        ]
        if summaries:
            # Use the complete value of the first authoritative summary.
            # Validation is applied to the field as a whole by the repair
            # planner; per-fragment filtering silently lost valid attributes.
            return True, remove_incomplete_trailing_dimension_field(
                normalize_detail_text(
                    self._detail_text_from_element(summaries[0]),
                    preserve_boundaries=preserve_boundaries,
                )
            )

        return False, ""

    def extract_detail_text(self, soup) -> str:
        """Use the identified Detail field before considering generic fallbacks."""
        field_found, detail = self.extract_authoritative_detail_text(
            soup,
            preserve_boundaries=True,
        )
        if field_found:
            return detail
        return self._extract_detail_text_fallback(soup)

    def _extract_detail_text_fallback(self, soup) -> str:
        """Extrae atributos etiquetados y elimina texto comercial y líneas de color."""
        for selector_group in self._DETAIL_SELECTORS_BY_PRIORITY:
            for selector in selector_group:
                for element in soup.select(selector):
                    if self._is_excluded_detail_tab(element):
                        continue
                    detail = self._validated_detail_candidate(
                        element,
                        require_multiple_fields=False,
                    )
                    if detail:
                        return detail

        # Before inspecting generic leaf nodes (such as a single <p>), combine
        # labeled sibling blocks from the same detail container. Otherwise the
        # first technical paragraph wins and the remaining fields are lost.
        labeled_details = self._extract_labeled_detail_blocks(soup)
        if labeled_details:
            return labeled_details

        for selector in self._DETAIL_FALLBACK_SELECTORS:
            for element in soup.select(selector):
                if self._is_excluded_detail_tab(element):
                    continue
                detail = self._validated_detail_candidate(
                    element,
                    require_multiple_fields=True,
                )
                if detail:
                    return detail

        return self._extract_semantic_detail_fields(soup)

    def extract_description(self, soup):
        """Conserva la API previa, pero el campo almacenado es Detalle técnico."""
        return self.extract_detail_text(soup)

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
        variant_color_stock = extract_variant_color_stock(soup)
        if variant_color_stock:
            return variant_color_stock

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
        for color in explicit_colors:
            add_color(color)

        self._extract_select_color_stock(soup, add_color)
        self._extract_element_color_stock(soup, add_color)
        self._extract_variation_color_stock(soup, add_color, color_labels)

        if color_stock and len(color_stock) == len(color_names):
            return color_stock

        if not color_stock and color_names:
            return {color: 0 for color in color_names}

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

    def extract_image(self, soup, *, base_url=""):
        code = self._extracted_codes.pop(id(soup), None)
        if code is None:
            code = self.extract_code(soup)
        candidates = ProductImageExtractor.extract_candidates(
            soup,
            code=code,
            name=self.extract_name(soup),
            base_url=base_url or self.BASE_URL,
        )
        return candidates[0]["url"] if candidates else ""

    def extract_image_candidates(self, soup, *, base_url=""):
        code = self._extracted_codes.get(id(soup))
        if code is None:
            code = self.extract_code(soup)
        return ProductImageExtractor.extract_candidates(
            soup,
            code=code,
            name=self.extract_name(soup),
            base_url=base_url or self.BASE_URL,
        )

    def _normalize_image_url(self, url):
        return ProductImageExtractor._normalize_url(
            url,
            base_url=self.BASE_URL,
        )
