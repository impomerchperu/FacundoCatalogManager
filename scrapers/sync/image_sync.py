from scrapers.images.image_manager import ImageManager
from scrapers.images.image_repository import ImageRepository


class ImageSync:
    """
    Sincronización incremental
    de imágenes de productos.

    Reglas:

    - Imagen inexistente:
        descarga.

    - Imagen existente:
        conserva archivo.

    - Imagen cambiada:
        descarga nuevamente.
    """


    def __init__(
        self,
        image_manager=None,
        image_repository=None,
    ):

        self.image_manager = (
            image_manager
            or ImageManager()
        )

        self.image_repository = (
            image_repository
            or ImageRepository()
        )


    def synchronize(
        self,
        product,
        old_product=None,
    ):

        result = self.sync_product(
            product,
            old_product,
        )

        return {
            "image_path": getattr(
                result,
                "image_path",
                "",
            ),
            "image_hash": getattr(
                result,
                "image_hash",
                "",
            ),
        }


    def process(
        self,
        products,
    ):

        return [
            self.sync_product(product)
            for product in products
        ]


    def sync_product(
        self,
        product,
        old_product=None,
    ):

        image_url = getattr(
            product,
            "image_url",
            "",
        )

        if not image_url:
            return product


        existing = self.image_repository.find(
            product.code
        )


        if existing:

            product.image_path = (
                existing["image_path"]
            )

            product.image_hash = (
                existing.get(
                    "image_hash",
                    "",
                )
            )

            return product



        image_data = self.image_manager.process(
            product.code,
            image_url,
        )


        product.image_path = (
            image_data.get(
                "image_path",
                "",
            )
        )

        product.image_hash = (
            image_data.get(
                "image_hash",
                "",
            )
        )


        return product
