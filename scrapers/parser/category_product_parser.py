from typing import Dict

from scrapers.factories.scraped_product_factory import (
    ScrapedProductFactory,
)


class CategoryProductParser:
    """
    Parser de productos encontrados dentro de páginas categoría WooCommerce.
    """

    def parse(
        self,
        product,
        url: str = "",
        category: str = "",
    ):

        if product is None:
            return None

        code = self.extract_code(product)

        name = self.extract_name(product)

        if not code and not name:
            return None

        prices = self.extract_prices(product)

        return ScrapedProductFactory.create(
            url=url,
            code=code,
            name=name,
            category=category,
            description=self.extract_description(
                product,
                name,
            ),
            stock=self.extract_stock(product),
            price_sample=prices["sample"],
            price_hundred=prices["hundred"],
            price_thousand=prices["thousand"],
            image_url=self.extract_image(product),
        )

    # --------------------------------------------------
    # Código
    # --------------------------------------------------

    def extract_code(
        self,
        product,
    ) -> str:

        element = product.find("p")

        return element.get_text(strip=True) if element else ""

    # --------------------------------------------------
    # Nombre
    # --------------------------------------------------

    def extract_name(
        self,
        product,
    ) -> str:

        element = product.find("h2")

        return element.get_text(strip=True) if element else ""

    # --------------------------------------------------
    # Imagen
    # --------------------------------------------------

    def extract_image(
        self,
        product,
    ) -> str:

        for image in product.find_all("img"):
            url = image.get("data-src") or image.get("src")

            if isinstance(url, str) and "FB-" in url:
                return url

        return ""

    # --------------------------------------------------
    # Descripción
    # --------------------------------------------------

    def extract_description(
        self,
        product,
        name: str,
    ) -> str:

        text = product.get_text(
            "\n",
        )

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        code = self.extract_code(product)

        ignored = {
            name,
            code,
            "Leer Más",
        }

        result = []

        for line in lines:
            if line in ignored:
                continue

            if "Precio" in line:
                continue

            if "Stock" in line:
                continue

            result.append(line)

        return "\n".join(result)

    # --------------------------------------------------
    # Precios
    # --------------------------------------------------

    def extract_prices(
        self,
        product,
    ) -> Dict[str, float]:

        prices = {
            "sample": 0.0,
            "hundred": 0.0,
            "thousand": 0.0,
        }

        for block in product.select(
            ".content-precio",
        ):
            title = block.find("h3")
            value = block.find("h4")

            if not title or not value:
                continue

            raw = value.text.replace("S/", "").replace(",", "").strip()

            try:
                number = float(raw)

            except ValueError:
                number = 0.0

            label = title.text.strip()

            if "Muestra" in label:
                prices["sample"] = number

            elif "Ciento" in label:
                prices["hundred"] = number

            elif "Millar" in label:
                prices["thousand"] = number

        return prices

    # --------------------------------------------------
    # Stock
    # --------------------------------------------------

    def extract_stock(
        self,
        product,
    ) -> int:

        return 0
