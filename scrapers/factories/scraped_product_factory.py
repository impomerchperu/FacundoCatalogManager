from models.scraping.scraped_product import ScrapedProduct
from scrapers.sync.content_hash import ContentHash


class ScrapedProductFactory:
    """Factory responsable de construir instancias de ScrapedProduct."""

    @staticmethod
    def create(
        *,
        source: str = "importacionesfacundo",
        url: str = "",
        code: str = "",
        name: str = "",
        category: str = "",
        description: str = "",
        stock: int = 0,
        price: float = 0.0,
        price_sample: float = 0.0,
        price_hundred: float = 0.0,
        price_thousand: float = 0.0,
        color_stock: dict[str, int] | None = None,
        image_url: str = "",
        image_path: str = "",
        image_hash: str = "",
        image_error: str = "",
    ) -> ScrapedProduct:
        product = ScrapedProduct(
            source=source,
            url=url,
            code=code,
            name=name,
            category=category,
            description=description,
            stock=stock,
            price=price,
            price_sample=price_sample,
            price_hundred=price_hundred,
            price_thousand=price_thousand,
            color_stock=color_stock or {},
            image_url=image_url,
            image_path=image_path,
            image_hash=image_hash,
            image_error=image_error,
        )

        product.content_hash = ContentHash.generate(product)
        return product
