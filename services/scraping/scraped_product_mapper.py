from models.product import Product
from models.scraping.scraped_product import ScrapedProduct
from services.scraping.product_hash_service import ProductHashService


class ScrapedProductMapper:
    """Convierte datos scrapeados al modelo interno del catálogo."""

    def __init__(self):
        self.hash_service = ProductHashService()

    def map(self, product, url: str | None = None):
        if isinstance(product, ScrapedProduct):
            return self.to_product(product)
        return self.from_html(product, url)

    def to_product(self, scraped_product: ScrapedProduct) -> Product:
        return Product(
            code=scraped_product.code,
            name=scraped_product.name,
            category=scraped_product.category,
            description=scraped_product.description,
            price=self._resolve_price(scraped_product),
            price_sample=scraped_product.price_sample,
            price_hundred=scraped_product.price_hundred,
            price_thousand=scraped_product.price_thousand,
            stock=scraped_product.stock,
            colors=list(scraped_product.colors),
            color_stock=dict(scraped_product.color_stock),
            image_url=scraped_product.image_url,
            image_path=scraped_product.image_path,
            image_hash=scraped_product.image_hash,
            content_hash=self.hash_service.generate(scraped_product),
        )

    def from_html(self, soup, url: str | None = None) -> ScrapedProduct:
        return ScrapedProduct(
            source="web",
            url=url if url else "",
            name=self._extract_name(soup),
        )

    @staticmethod
    def _resolve_price(product: ScrapedProduct) -> float:
        if product.price_sample > 0:
            return product.price_sample
        return product.price

    @staticmethod
    def _extract_name(soup) -> str:
        for selector in ["h1", "title"]:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(" ", strip=True)
                if text:
                    return text
        return ""
