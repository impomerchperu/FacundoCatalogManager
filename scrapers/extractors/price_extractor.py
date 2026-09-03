import re
from typing import ClassVar


class PriceExtractor:
    """Extrae los tres precios de las tarjetas de producto."""

    _FIELDS: ClassVar[dict[str, str]] = {
        "muestra": "sample",
        "ciento": "hundred",
        "millar": "thousand",
    }

    def _extract_price_block(self, soup, label):
        """Extrae un precio a partir de un bloque etiquetado."""
        blocks = soup.select(".content-precio")
        label_normalized = label.casefold()

        for block in blocks:
            title = block.find(["h3", "h4"])
            if title is None:
                continue

            title_text = " ".join(title.get_text(" ", strip=True).split())
            if label_normalized not in title_text.casefold():
                continue

            value = block.find_all(["h3", "h4"])
            for element in reversed(value):
                if element is title:
                    continue
                price = self._parse_price(element.get_text(" ", strip=True))
                if price is not None:
                    return price

            price = self._parse_price(block.get_text(" ", strip=True))
            if price is not None:
                return price

        heading = soup.find(
            lambda tag: tag.name in ["h3", "h4"]
            and label_normalized in tag.get_text(" ", strip=True).casefold()
        )
        if heading is not None:
            price = heading.find_next("h4")
            if price is not None:
                parsed = self._parse_price(price.get_text(" ", strip=True))
                if parsed is not None:
                    return parsed

        return self._extract_labeled_price_from_text(soup, label)

    def _extract_labeled_price_from_text(self, soup, label):
        """Recupera el importe aunque la plantilla no conserve clases CSS."""
        text = " ".join(soup.stripped_strings)
        pattern = re.compile(
            rf"{re.escape(label)}\s*[:\-]?\s*"
            rf"(?:S/|US\$|USD|\$)?\s*([\d][\d,.]*)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match is None:
            return 0.0
        return self._parse_price(match.group(1)) or 0.0

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
            raw = raw.replace(",", ".")

        try:
            return float(raw)
        except ValueError:
            return None

    def extract_sample(self, soup):
        return self._extract_price_block(soup, "Precio Muestra")

    def extract_hundred(self, soup):
        return self._extract_price_block(soup, "Precio Ciento")

    def extract_thousand(self, soup):
        return self._extract_price_block(soup, "Precio Millar")
