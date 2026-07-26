class Product:
    def __init__(
        self,
        code,
        name,
        category="",
        description="",
        price=0,
        stock=0,
        image_path="",
        product_id=None,
    ):
        self.id = product_id
        self.code = code
        self.name = name
        self.category = category
        self.description = description
        self.price = price
        self.stock = stock
        self.image_path = image_path