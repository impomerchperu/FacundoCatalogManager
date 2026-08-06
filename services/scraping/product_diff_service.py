from services.scraping.product_hash_service import ProductHashService


class ProductDiffService:
    """
    Detecta diferencias entre dos productos.

    Estrategia:

    1. Si ambos poseen content_hash:
       comparar hashes.

    2. Si alguno no posee hash:
       comparar todos los campos
       relevantes.
    """

    def __init__(self):
        self.hash_service = ProductHashService()

        self.fields = [
            "code",
            "name",
            "category",
            "description",
            "price",
            "price_sample",
            "price_hundred",
            "price_thousand",
            "stock",
            "image_url",
        ]

    def compare(
        self,
        old_product,
        new_product,
    ):
        old_hash = self._value(
            old_product,
            "content_hash",
        )

        new_hash = self._value(
            new_product,
            "content_hash",
        )

        if (
            old_hash
            and new_hash
            and old_hash == new_hash
        ):
            return {
                "changed": False,
                "fields": [],
            }

        changed_fields = []

        for field in self.fields:
            if (
                self._value(old_product, field)
                != self._value(new_product, field)
            ):
                changed_fields.append(field)

        return {
            "changed": bool(changed_fields),
            "fields": changed_fields,
        }

    def has_changes(
        self,
        old_product,
        new_product,
    ) -> bool:
        """
        Método de compatibilidad.

        Permite que el resto del proyecto
        consulte simplemente si existen
        cambios entre dos productos.
        """
        return self.compare(
            old_product,
            new_product,
        )["changed"]

    def _value(
        self,
        obj,
        field,
    ):
        """
        Compatible con:

        - dict
        - Product
        - ScrapedProduct
        - objetos Fake
        """

        if isinstance(
            obj,
            dict,
        ):
            return obj.get(field)

        return getattr(
            obj,
            field,
            None,
        )
