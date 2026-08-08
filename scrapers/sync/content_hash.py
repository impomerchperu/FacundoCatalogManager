import hashlib


class ContentHash:
    """
    Genera un hash SHA256 del contenido
    relevante de un producto.

    Si cualquier dato cambia
    (nombre, precio, stock, descripción...)
    el hash también cambia.
    """

    FIELDS = (
        "code",
        "name",
        "category",
        "description",
        "stock",
        "price_sample",
        "price_hundred",
        "price_thousand",
    )

    @classmethod
    def generate(cls, product):

        values = []

        for field in cls.FIELDS:
            value = getattr(product, field, "")
            values.append(str(value).strip())

        text = "|".join(values)

        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()
