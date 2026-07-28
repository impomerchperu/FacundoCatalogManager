from database.db_manager import add_product, get_products, initialize_database
from models.product import Product

initialize_database()

product = Product(
    code="P001",
    name="Producto de prueba",
    category="General",
    description="Primer registro del catálogo",
    price=25.50,
    stock=10,
)

add_product(product)

products = get_products()

for item in products:
    print(item)
