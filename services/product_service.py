from models.product import Product
from repositories.product_repository import ProductRepository


class ProductService:
    def __init__(
        self,
        repository: ProductRepository | None = None,
    ) -> None:
        self.repository = repository or ProductRepository()

    def create_product(
        self,
        product: Product,
    ) -> Product:
        product.normalize()

        errors = product.validate()

        if errors:
            raise ValueError(errors)

        return self.repository.create(
            product,
        )

    def update_product(
        self,
        product: Product,
    ) -> Product:
        product.normalize()

        errors = product.validate()

        if errors:
            raise ValueError(errors)

        return self.repository.update(
            product,
        )

    def save_product(
        self,
        product: Product,
    ) -> Product:
        product.normalize()

        errors = product.validate()

        if errors:
            raise ValueError(errors)

        return self.repository.save(
            product,
        )

    def delete_product(
        self,
        product_id: int,
    ) -> None:
        self.repository.delete(
            product_id,
        )

    def get_products(self) -> list[Product]:
        return self.repository.get_all()

    def search_products(
        self,
        text: str,
    ) -> list[Product]:
        return self.repository.search(
            text,
        )

    def get_product_by_id(
        self,
        product_id: int,
    ) -> Product | None:
        return self.repository.get_by_id(
            product_id,
        )
