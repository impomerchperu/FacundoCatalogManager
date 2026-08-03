from scrapers.images.image_manager import ImageManager
from scrapers.storage.product_comparator import ProductComparator
from scrapers.storage.product_storage import ProductStorage


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
        image_manager=None,
    ):

        self.storage = storage or ProductStorage()

        self.comparator = comparator or ProductComparator()

        self.image_manager = image_manager or ImageManager()

    def synchronize(self, products):

        # ---------------------------------------------
        # 1. Leer estado actual
        # ---------------------------------------------

        old_products = self.storage.load()

        # ---------------------------------------------
        # 2. Comparar productos
        # ---------------------------------------------

        result = self.comparator.compare(old_products, products)

        # ---------------------------------------------
        # 3. Procesar imágenes solamente necesarias
        # ---------------------------------------------

        products = self._merge_images(products, old_products, result)

        # ---------------------------------------------
        # 4. Guardar estado final
        # ---------------------------------------------

        self.storage.save(products)

        return result

    def _merge_images(
        self,
        products,
        old_products,
        result,
    ):

        old_map = {p["code"]: p for p in old_products if p.get("code")}

        changed_codes = {
            product.code for product in (result["new"] + result["updated"])
        }

        processed = []

        for product in products:
            # -----------------------------------------
            # Producto sin cambios:
            # conservar imagen existente
            # -----------------------------------------

            if product.code not in changed_codes:
                old = old_map.get(product.code)

                if old:
                    product.image_path = old.get("image_path", "")

                    product.image_hash = old.get("image_hash", "")

                processed.append(product)

                continue

            # -----------------------------------------
            # Producto nuevo/modificado:
            # procesar imagen
            # -----------------------------------------

            image_data = self.image_manager.process(
                product.code,
                product.image_url,
            )

            product.image_path = image_data.get("image_path", "")

            product.image_hash = image_data.get("image_hash", "")

            processed.append(product)

        return processed
