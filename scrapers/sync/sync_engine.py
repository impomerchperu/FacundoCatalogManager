from scrapers.storage.product_comparator import ProductComparator
from scrapers.storage.product_storage import ProductStorage
from scrapers.sync.image_sync import ImageSync


class SyncEngine:
    """
    Motor principal de sincronización.

    Flujo:

    Productos scrapeados
            |
            v
    Comparación con storage actual
            |
            +--> Nuevos
            |
            +--> Actualizados
            |
            +--> Sin cambios

    Solo nuevos y actualizados
    pasan por procesamiento de imágenes.
    """

    def __init__(
        self,
        storage=None,
        comparator=None,
        image_sync=None,
    ):
        self.storage = storage or ProductStorage()

        self.comparator = (
            comparator
            or ProductComparator()
        )

        self.image_sync = (
            image_sync
            or ImageSync()
        )

    def synchronize(
        self,
        products,
    ):

        old_products = self.storage.load()

        result = self.comparator.compare(
            old_products,
            products,
        )

        products = self._merge_images(
            products,
            old_products,
            result,
        )

        self.storage.save(products)

        return result

    def _merge_images(
        self,
        products,
        old_products,
        result,
    ):

        old_map = {
            product["code"]: product
            for product in old_products
            if product.get("code")
        }

        changed_codes = {
            product.code
            for product in (
                result["new"]
                +
                result["updated"]
            )
        }

        processed = []

        for product in products:

            old = old_map.get(
                product.code,
            )

            # Producto sin cambios:
            # conservar imagen existente

            if product.code not in changed_codes:

                if old:

                    product.image_path = old.get(
                        "image_path",
                        "",
                    )

                    product.image_hash = old.get(
                        "image_hash",
                        "",
                    )

                processed.append(product)

                continue


            # Producto nuevo/modificado:
            # sincronizar imagen

            product = self.image_sync.sync_product(
                product,
                old,
            )

            processed.append(product)

        return processed
