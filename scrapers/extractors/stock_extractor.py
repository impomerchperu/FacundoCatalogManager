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

        fragment = re.split(
            r"(?:Precio|Código|Imagen|Producto|Descripción)",
            parts[1],
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        values: list[int] = []
        for raw_value in re.findall(r"\d[\d,.]*", fragment):
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
