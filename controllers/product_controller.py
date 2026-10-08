from models.product import Product
from services.product_service import ProductService


class ProductController:
    def __init__(
        self,
        service: ProductService | None = None,
    ) -> None:
        self.service = service

    def _get_service(self) -> ProductService:
        if self.service is None:
            self.service = ProductService()
        return self.service

    def _refresh_read_service(self) -> None:
        """Reabre la lectura del catálogo para recoger commits externos recientes."""
        self.service = ProductService()

    def get_products(self) -> list[Product]:
        self._refresh_read_service()
        return self._get_service().get_products()

    def create_product(
        self,
        product: Product,
    ) -> Product:
        return self._get_service().create_product(
            product,
        )

    def update_product(
        self,
        product: Product,
    ) -> Product:
        return self._get_service().update_product(
            product,
        )

    def save_product(
        self,
        product: Product,
    ) -> Product:
        return self._get_service().save_product(
            product,
        )

    def save_products(self, products: list[Product]) -> list[Product]:
        return self._get_service().save_products(products)

    def delete_product(
        self,
        product_id: int,
    ) -> None:
        self._get_service().delete_product(
            product_id,
        )

    def rename_category(self, category_name: str, new_name: str) -> int:
        return self._get_service().rename_category(
            category_name,
            new_name,
        )

    def delete_category(self, category_name: str) -> int:
        return self._get_service().delete_category(category_name)

    def search_products(
        self,
        text: str,
    ) -> list[Product]:
        return self._get_service().search_products(
            text,
        )

    def get_product_by_id(
        self,
        product_id: int,
    ) -> Product | None:
        return self._get_service().get_product_by_id(
            product_id,
        )
