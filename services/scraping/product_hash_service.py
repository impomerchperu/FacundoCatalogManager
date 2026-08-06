import hashlib
import json
from typing import ClassVar


class ProductHashService:
    """
    Genera hashes para detectar cambios
    en productos e imágenes.
    """

    CONTENT_FIELDS: ClassVar[list[str]] = [
        "code",
        "name",
        "category",
        "description",
        "price",
        "price_sample",
        "price_hundred",
        "price_thousand",
        "stock",
    ]

    IMAGE_FIELDS: ClassVar[list[str]] = [
        "image_url",
        "image_path",
    ]


    def generate(
        self,
        product,
    ) -> str:
        """
        Compatibilidad:
        genera hash completo del producto.
        """

        return self.generate_content_hash(
            product,
        )


    def generate_content_hash(
        self,
        product,
    ) -> str:
        """
        Hash de información comercial.
        """

        return self._generate_hash(
            product,
            self.CONTENT_FIELDS,
        )


    def generate_image_hash(
        self,
        product,
    ) -> str:
        """
        Hash relacionado con imagen.
        """

        return self._generate_hash(
            product,
            self.IMAGE_FIELDS,
        )


    def _generate_hash(
        self,
        product,
        fields,
    ) -> str:

        data = {}

        for field in fields:

            data[field] = self._normalize(
                self._get_value(
                    product,
                    field,
                )
            )


        payload = json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False,
        )


        return hashlib.sha256(
            payload.encode(
                "utf-8",
            )
        ).hexdigest()



    def _get_value(
        self,
        product,
        field,
    ):

        if isinstance(
            product,
            dict,
        ):

            return product.get(
                field,
            )


        return getattr(
            product,
            field,
            None,
        )


    def _normalize(
        self,
        value,
    ):

        if isinstance(
            value,
            str,
        ):

            return value.strip()


        return value
