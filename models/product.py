from dataclasses import dataclass


@dataclass
class Product:
    """
    Modelo que representa un producto del catálogo.
    """

    code: str
    name: str
    category: str
    description: str
    price: float
    stock: int
    image_path: str = ""
    product_id: int | None = None

    @property
    def id(self):

        return self.product_id

    @id.setter
    def id(self, value):

        self.product_id = value

    def validate(self):

        errors = []

        if not self.code or not self.code.strip():
            errors.append("El código es obligatorio")

        if not self.name or not self.name.strip():
            errors.append("El nombre es obligatorio")

        if self.price < 0:
            errors.append("El precio no puede ser negativo")

        if self.stock < 0:
            errors.append("El stock no puede ser negativo")

        return errors

    def normalize(self):

        self.code = self.code.strip()

        self.name = self.name.strip()

        self.category = self.category.strip()

        self.description = self.description.strip()

        return self

    def is_valid(self):

        return len(self.validate()) == 0
