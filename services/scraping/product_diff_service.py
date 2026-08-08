from services.scraping.product_hash_service import ProductHashService


class ProductDiffService:
    """
    Detecta diferencias entre productos.

    Separa:

    - cambios comerciales
    - cambios de imagen
    """

    def __init__(self):

        self.hash_service = ProductHashService()

        self.content_fields = (
            self.hash_service.CONTENT_FIELDS
        )

        self.image_fields = (
            self.hash_service.IMAGE_FIELDS
        )


    def compare(
        self,
        old_product,
        new_product,
    ):

        changed_fields = []


        for field in (
            list(self.content_fields)
            +
            list(self.image_fields)
        ):

            if (
                self._value(old_product, field)
                !=
                self._value(new_product, field)
            ):

                changed_fields.append(
                    field
                )


        content_changed = any(
            field in self.content_fields
            for field in changed_fields
        )


        image_changed = any(
            field in self.image_fields
            for field in changed_fields
        )


        return {
            "changed": bool(changed_fields),
            "fields": changed_fields,
            "content_changed": content_changed,
            "image_changed": image_changed,
        }


    def has_changes(
        self,
        old_product,
        new_product,
    ):

        return self.compare(
            old_product,
            new_product,
        )["changed"]


    def _value(
        self,
        obj,
        field,
    ):

        if isinstance(
            obj,
            dict,
        ):
            return obj.get(
                field
            )

        return getattr(
            obj,
            field,
            None,
        )
