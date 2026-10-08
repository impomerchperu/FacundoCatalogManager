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

        created = self.repository.create(
            product,
        )
        self.repository.sync_product_categories(created.id, created.category)
        return created

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
        except Exception:
            self.repository.db.rollback()
            raise
        else:
            self.repository.db.commit()
            return created

    def update_product(
        self,
        product: Product,
    ) -> Product:
        product.normalize()

        errors = product.validate()

        if errors:
            raise ValueError(errors)

        updated = self.repository.update(
            product,
        )
        self.repository.sync_product_categories(updated.id, updated.category)
        return updated

    def save_product(
        self,
        product: Product,
    ) -> Product:
        product.normalize()

        errors = product.validate()

        if errors:
            raise ValueError(errors)

        saved = self.repository.save(
            product,
        )
        self.repository.sync_product_categories(saved.id, saved.category)
        return saved

    def save_products(
        self,
        products: list[Product],
    ) -> list[Product]:
        """Create or replace a product batch atomically."""
        if not products:
            return []

        self.repository.db.begin()
        try:
            saved: list[Product] = []
            for product in products:
                existing = self.repository.get_by_code(product.code)
                if existing is not None:
                    product.product_id = existing.id
                    if not product.gallery_images and not product.image_path:
                        product.image_url = existing.image_url
                        product.image_path = existing.image_path
                        product.image_hash = existing.image_hash
                        product.gallery_images = [
                            dict(image)
                            for image in existing.gallery_images
                            if isinstance(image, dict)
                        ]
                saved.append(self.save_product(product))
        except Exception:
            self.repository.db.rollback()
            raise
        else:
            self.repository.db.commit()
            return saved

    def rename_category(
        self,
        category_name: str,
        new_name: str,
    ) -> int:
        return self.repository.rename_category(category_name, new_name)

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
