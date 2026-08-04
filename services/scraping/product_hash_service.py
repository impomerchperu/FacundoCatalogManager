import hashlib
import json
from typing import ClassVar


class ProductHashService:
    """
    Genera una firma única del contenido
    de un producto.

    Permite detectar cambios
    durante sincronizaciones incrementales.
    """

    FIELDS: ClassVar[list[str]] = [
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

    def generate(
        self,
        product,
    ) -> str:
        """
        Genera hash SHA256 estable.
        """

        data = {}

        for field in self.FIELDS:
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
            payload.encode("utf-8")
        ).hexdigest()

    def _get_value(
        self,
        product,
        field,
    ):
        """
        Obtiene valores desde:

        - objetos
        - diccionarios
        """

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
        """
        Normaliza valores para evitar
        falsos cambios.
        """

        if isinstance(
            value,
            str,
        ):
            return value.strip()

        return value
