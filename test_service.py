from services.product_service import ProductService
from models.product import Product


service = ProductService()

producto = Product(
    code="P002",
    name="Segundo producto",
    category="General",
    description="Producto creado mediante servicio",
    price=35.90,
    stock=5,
    image_path=""
)

service.create_product(producto)


productos = service.get_products()

for p in productos:
    print(p)