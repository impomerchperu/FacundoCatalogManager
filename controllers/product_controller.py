from models.product import Product
from services.product_service import ProductService


class ProductController:
    def __init__(
        self,
        service: ProductService | None = None,
    ) -> None:
        self.service = service or ProductService()

    def get_products(self) -> list[Product]:
        return self.service.get_products()

    def create_product(
        self,
        product: Product,
    ) -> Product:
        return self.service.create_product(
            product,
        )

    def update_product(
        self,
        product: Product,
    ) -> Product:
        return self.service.update_product(
            product,
        )

    def save_product(
        self,
        product: Product,
    ) -> Product:
        return self.service.save_product(
            product,
        )

    def delete_product(
        self,
        product_id: int,
    ) -> None:
        self.service.delete_product(
            product_id,
        )

    def search_products(
        self,
        text: str,
    ) -> list[Product]:
        return self.service.search_products(
            text,
        )

    def get_product_by_id(
        self,
        product_id: int,
    ) -> Product | None:
        return self.service.get_product_by_id(
            product_id,
        )
