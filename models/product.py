from dataclasses import dataclass


@dataclass
class Product:
    """
    Modelo principal del catálogo.
    Compatible con CRUD y sincronización.
    """

    code: str
    name: str

    price: float = 0

    category: str = ""
    description: str = ""

    price_sample: float = 0
    price_hundred: float = 0
    price_thousand: float = 0

    stock: int = 0

    image_url: str = ""
    image_path: str = ""
    image_hash: str = ""

    content_hash: str = ""

    product_id: int | None = None

    @property
    def id(self) -> int | None:
        return self.product_id

    @id.setter
    def id(self, value: int | None) -> None:
        self.product_id = value

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.code.strip():
            errors.append(
                "El código es obligatorio",
            )

        if not self.name.strip():
            errors.append(
                "El nombre es obligatorio",
            )

        if self.price < 0:
            errors.append(
                "El precio no puede ser negativo",
            )

        if self.price_sample < 0:
            errors.append(
                "El precio muestra no puede ser negativo",
            )

        if self.price_hundred < 0:
            errors.append(
                "El precio ciento no puede ser negativo",
            )

        if self.price_thousand < 0:
            errors.append(
                "El precio millar no puede ser negativo",
            )

        if self.stock < 0:
            errors.append(
                "El stock no puede ser negativo",
            )

        return errors

    def normalize(self) -> "Product":
        self.code = self.code.strip()
        self.name = self.name.strip()

        self.category = str(
            self.category,
        ).strip()

        self.description = self.description.strip()

        self.image_url = self.image_url.strip()
        self.image_path = self.image_path.strip()
        self.image_hash = self.image_hash.strip()
        self.content_hash = self.content_hash.strip()

        return self

    def is_valid(self) -> bool:
        return len(self.validate()) == 0
