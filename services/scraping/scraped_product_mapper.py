from models.product import Product
from models.scraping.scraped_product import ScrapedProduct
from services.scraping.product_hash_service import ProductHashService


class ScrapedProductMapper:
    """
    Convierte datos scrapeados al modelo interno del catálogo.
    """

    def __init__(self):
        self.hash_service = ProductHashService()

    def map(
        self,
        product,
        url: str | None = None,
    ):
        """
        Convierte productos scrapeados.

        Soporta:

        1. ScrapedProduct -> Product

        2. BeautifulSoup -> ScrapedProduct
        """

        if isinstance(product, ScrapedProduct):
            return self.to_product(product)

        return self.from_html(
            product,
            url,
        )

    def to_product(
        self,
        scraped_product: ScrapedProduct,
    ) -> Product:
        """
        Convierte un producto scrapeado
        al modelo principal del catálogo.
        """

        return Product(
            code=scraped_product.code,
            name=scraped_product.name,
            category=scraped_product.category,
            description=scraped_product.description,
            price=self._resolve_price(
                scraped_product,
            ),
            price_sample=scraped_product.price_sample,
            price_hundred=scraped_product.price_hundred,
            price_thousand=scraped_product.price_thousand,
            stock=scraped_product.stock,
            image_url=scraped_product.image_url,
            image_path=scraped_product.image_path,
            content_hash=self.hash_service.generate(
                scraped_product,
            ),
        )

    def from_html(
        self,
        soup,
        url: str | None = None,
    ) -> ScrapedProduct:
        """
        Convierte HTML en ScrapedProduct.
        """

        return ScrapedProduct(
            source="web",
            url=url if url else "",
            name=self._extract_name(
                soup,
            ),
        )

    def _resolve_price(
        self,
        product: ScrapedProduct,
    ) -> float:
        """
        Obtiene el precio principal.

        Prioridad:

        1. Precio muestra.
        2. Precio general.
        """

        if product.price_sample > 0:
            return product.price_sample

        return product.price

    def _extract_name(
        self,
        soup,
    ) -> str:
        """
        Extrae nombre desde HTML.
        """

        selectors = [
            "h1",
            "title",
        ]

        for selector in selectors:
            element = soup.select_one(
                selector,
            )

            if element:
                text = element.get_text(
                    " ",
                    strip=True,
                )

                if text:
                    return text

        return ""
