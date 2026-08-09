import hashlib


class ContentHash:
    """Genera un hash SHA256 del contenido relevante de un producto."""

    FIELDS = (
        "code",
        "name",
        "category",
        "description",
        "stock",
        "price_sample",
        "price_hundred",
        "price_thousand",
        "colors",
        "color_stock",
    )

    @classmethod
    def generate(cls, product):
        values = []

        for field in cls.FIELDS:
            value = getattr(product, field, "")
            if isinstance(value, dict):
                value = sorted(value.items())
            elif isinstance(value, (list, tuple, set)):
                value = sorted(value)
            values.append(str(value).strip())

        text = "|".join(values)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
