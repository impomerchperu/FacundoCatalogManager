from models.product import Product
from repositories.product_repository import ProductRepository


class ProductService:
    def __init__(
        self,
        repository: ProductRepository | None = None,
    ) -> None:
        self.repository = repository or ProductRepository()

    def next_product_code(self) -> str:
        """Return the next available code for a manually created product."""
        return self.repository.next_product_code()

    def create_product(
        self,
        product: Product,
    ) -> Product:
        if not product.code.strip():
            product.code = self.repository.next_product_code()
        product.normalize()

        errors = product.validate()

        if errors:
            raise ValueError(errors)

        return self.repository.create(
            product,
        )

    def create_products(
        self,
        products: list[Product],
    ) -> list[Product]:
        """Create a validated batch atomically."""
        if not products:
            return []

        self.repository.db.begin()
        try:
            created: list[Product] = []
            for product in products:
                created.append(self.create_product(product))
            self.repository.db.commit()
            return created
        except Exception:
            self.repository.db.rollback()
            raise

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

    def delete_category(self, category_name: str) -> int:
        return self.repository.delete_category(category_name)

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
