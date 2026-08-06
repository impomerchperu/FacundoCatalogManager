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
            if marker in text:
                value = self._extract_number_after_marker(
                    text,
                    marker,
                )

                if value is not None:
                    return value

        return 0

    def _extract_number_after_marker(
        self,
        text: str,
        marker: str,
    ) -> int | None:

        fragment = text.split(
            marker,
            1,
        )[1]

        numbers = "".join(
            char
            for char in fragment
            if char.isdigit()
        )

        if not numbers:
            return None

        return int(numbers)
