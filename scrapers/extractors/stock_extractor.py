import re
from typing import ClassVar


class StockExtractor:
    """
    Extrae disponibilidad de stock
    desde tarjetas o páginas de producto.
    """

    MARKERS: ClassVar[list[str]] = [
        "Stock Disponible",
        "Stock disponible",
        "Stock",
    ]

    def extract(self, soup) -> int:
        text = soup.get_text(
            " ",
            strip=True,
        )

        for marker in self.MARKERS:
            values = self._extract_numbers_after_marker(
                text,
                marker,
            )
            if values:
                return sum(values)

        return 0

    def _extract_numbers_after_marker(
        self,
        text: str,
        marker: str,
    ) -> list[int]:
        parts = text.split(marker, 1)
        if len(parts) != 2:
            return []

        match = re.match(
            r"\s*((?:\d[\d,.]*\s*)+)",
            parts[1],
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

    def _extract_number_after_marker(
        self,
        text: str,
        marker: str,
    ) -> int | None:
        values = self._extract_numbers_after_marker(text, marker)
        return values[0] if values else None
