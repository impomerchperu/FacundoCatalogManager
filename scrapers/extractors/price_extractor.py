import re
from typing import ClassVar


class PriceExtractor:
    """Extrae los tres precios de las tarjetas de producto."""

    _PRICE_LABELS: ClassVar[tuple[str, ...]] = (
        "Precio Muestra",
        "Precio Ciento",
        "Precio Millar",
        "Precio Caja",
        "Precio Por Caja",
        "Precio por 01 Paquete",
        "Precio por Paquete",
        "Precio por Unidad",
        "Precio Unidad",
        "Precio por 01 Caja",
        "Precio por Caja",
        "Precio Mayorista",
        "Precio por 01 Millar",
        "Precio por Millar",
    )
    _PRICE_FIELDS: ClassVar[tuple[str, ...]] = (
        "sample",
        "hundred",
        "thousand",
    )
    _PRICE_FIELD_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "sample": (
            "precio muestra",
            "precio por 01 paquete",
            "precio por paquete",
            "precio por unidad",
            "precio unidad",
        ),
        "hundred": (
            "precio ciento",
            "precio caja",
            "precio por caja",
            "precio por 01 caja",
            "precio mayorista",
        ),
        "thousand": (
            "precio millar",
            "precio por 01 millar",
            "precio por millar",
        ),
    }
    _CANONICAL_LABELS: ClassVar[dict[str, str]] = {
        "sample": "precio muestra",
        "hundred": "precio ciento",
        "thousand": "precio millar",
    }

    @classmethod
    def _field_key(cls, field_or_label: str) -> str:
        normalized = str(field_or_label).casefold().strip()
        if normalized in cls._PRICE_FIELD_ALIASES:
            return normalized
        for field, aliases in cls._PRICE_FIELD_ALIASES.items():
            if normalized in aliases:
                return field
        return normalized

    @classmethod
    def _field_aliases(cls, field_or_label: str) -> tuple[str, ...]:
        field = cls._field_key(field_or_label)
        aliases = cls._PRICE_FIELD_ALIASES.get(field)
        if aliases is not None:
            return aliases
        return (field,)

    def _extract_price_block(self, soup, label):
        """Extrae un nivel de precio con las etiquetas actuales e históricas."""
        value = self._find_price_value(soup, label)
        return 0.0 if value is None else value

    def _find_price_value(self, soup, field_or_label) -> float | None:
        field = self._field_key(field_or_label)
        aliases = self._field_aliases(field)

        heading = soup.find(
            lambda tag: tag.name in ["h3", "h4"]
            and any(
                alias in tag.get_text(" ", strip=True).casefold()
                for alias in aliases
            )
        )
        if heading is not None:
            price = self._next_labeled_price(heading, set(aliases))
            if price is not None:
                return price

        blocks = soup.select(".content-precio")
        for block in blocks:
            title = block.find(["h3", "h4"])
            if title is None:
                continue
            title_text = " ".join(title.get_text(" ", strip=True).split()).casefold()
            if not any(alias in title_text for alias in aliases):
                continue
            price = self._price_from_elements(block.find_all(["h3", "h4"]))
            if price is not None:
                return price
            price = self._price_from_text(block.get_text(" ", strip=True))
            if price is not None:
                return price

        table_price = self._extract_table_row_price(
            soup,
            self._CANONICAL_LABELS.get(field, field),
        )
        if table_price is not None:
            return table_price

        return self._extract_labeled_price_from_text(soup, aliases)

    def price_field_needs_recovery(self, soup, field: str) -> bool:
        """Indica si el HTML anuncia un nivel sin proporcionar un importe."""
        field_key = self._field_key(field)
        if self._find_price_value(soup, field_key) is not None:
            return False

        aliases = self._field_aliases(field_key)
        return any(
            alias in " ".join(soup.stripped_strings).casefold()
            for alias in aliases
        )

    def _next_labeled_price(self, heading, current_aliases):
        """Busca el importe siguiente sin saltar a otro nivel de precio."""
        for element in heading.find_all_next(["h3", "h4", "div", "span"]):
            text = " ".join(element.get_text(" ", strip=True).split())
            if self._contains_other_price_label(text, current_aliases):
                break
            if element.name in ["h3", "h4"]:
                price = self._parse_price(element.get_text(" ", strip=True))
                if price is not None:
                    return price
            if element.name in ["div", "span"]:
                price = self._price_from_text(text)
                if price is not None:
                    return price
        return None

    @classmethod
    def _contains_other_price_label(cls, text, current_aliases):
        normalized = text.casefold()
        return any(
            alias not in current_aliases and alias in normalized
            for aliases in cls._PRICE_FIELD_ALIASES.values()
            for alias in aliases
        )

    @staticmethod
    def _price_from_elements(elements):
        for element in reversed(elements):
            price = PriceExtractor._parse_price(element.get_text(" ", strip=True))
            if price is not None:
                return price
        return None

    @staticmethod
    def _price_from_text(text):
        matches = re.findall(
            r"(?:S/|US\$|USD|\$)\s*([\d][\d,.]*)",
            text,
            flags=re.IGNORECASE,
        )
        if matches:
            return PriceExtractor._parse_price(matches[-1])
        return None

    @staticmethod
    def _table_rows(soup):
        """Obtiene las filas de tabla relevantes para la tarjeta."""
        rows = []
        if getattr(soup, "name", "") == "tr":
            rows.append(soup)
        rows.extend(soup.select("tr.jsfb-filterable"))
        if not rows:
            rows.extend(soup.select("table tbody tr"))
        return rows

    def _extract_table_row_price(self, soup, label_normalized):
        """Recupera precios de filas Bricks aunque cambie el markup de las celdas."""
        for row in self._table_rows(soup):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 3:
                continue
            price_cells = self._table_price_cells(cells)
            price = self._match_table_price(price_cells, label_normalized)
            if price is not None:
                return price
        return None

    def _table_price_cells(self, cells):
        """Extrae importes de las columnas de precios de la tabla."""
        price_cells = []
        for cell in cells:
            text = " ".join(cell.stripped_strings)
            value = self._price_from_text(text)
            if value is None:
                continue
            price_cells.append((text.casefold(), value))
        return price_cells

    @staticmethod
    def _match_table_price(price_cells, label_normalized):
        """Selecciona el importe correspondiente al nivel solicitado."""
        matchers = {
            "precio muestra": r"\bmenos de\s+\d+\s+unidades?\b",
            "precio ciento": r"\ba partir(?: de)?\s+50\s+unidades?\b",
            "precio millar": r"\ba partir(?: de)?\s+500\s+unidades?\b",
            "precio caja": r"\ba partir(?: de)?\s+\d+\s+unidades?\b",
            "precio por caja": r"\ba partir(?: de)?\s+\d+\s+unidades?\b",
        }
        pattern = matchers.get(label_normalized)
        if pattern is not None:
            for text, value in price_cells:
                if re.search(pattern, text):
                    return value

        positions = {
            "precio muestra": 0,
            "precio ciento": 1,
            "precio caja": 1,
            "precio por caja": 1,
            "precio millar": 2,
        }
        position = positions.get(label_normalized)
        if position is not None and position < len(price_cells):
            return price_cells[position][1]
        return None

    def _extract_labeled_price_from_text(self, soup, aliases):
        """Recupera el importe cuando solo queda texto etiquetado."""
        text = " ".join(soup.stripped_strings)
        alternatives = "|".join(
            re.escape(alias)
            for alias in sorted(aliases, key=len, reverse=True)
        )
        pattern = re.compile(
            rf"(?:{alternatives})\s*[:\-]?\s*"
            rf"(?:S/|US\$|USD|\$)?\s*([\d][\d,.]*)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match is None:
            return None
        return self._parse_price(match.group(1))

    @staticmethod
    def _parse_price(text):
        """Convierte importes monetarios comunes del sitio a float."""
        cleaned = text.replace("S/", "").replace("US$", "")
        cleaned = cleaned.replace("USD", "").replace("$", "").strip()

        match = re.search(r"\d[\d,.]*", cleaned)
        if match is None:
            return None

        raw = match.group(0)
        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        elif "," in raw:
            if re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw):
                raw = raw.replace(",", "")
            else:
                raw = raw.replace(",", ".")

        try:
            return float(raw)
        except ValueError:
            return None

    def extract_sample(self, soup):
        return self._extract_price_block(soup, "sample")

    def extract_hundred(self, soup):
        return self._extract_price_block(soup, "hundred")

    def extract_thousand(self, soup):
        return self._extract_price_block(soup, "thousand")
