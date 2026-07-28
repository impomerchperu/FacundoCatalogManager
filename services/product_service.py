from models.product import Product
from repositories.product_repository import ProductRepository


class ProductService:
    def __init__(self):
        self.repository = ProductRepository()

    def create_product(self, product):
        self.repository.create(product)

    def update_product(self, product):
        self.repository.update(product)

    def delete_product(self, product_id):
        self.repository.delete(product_id)

    def get_products(self):
        return self.repository.get_all()

    def search_products(self, text):
        return self.repository.search(text)

    def get_product_by_id(self, product_id):

        data = self.repository.get_by_id(product_id)

        if not data:
            return None

        return Product(
            code=data[1],
            name=data[2],
            category=data[3],
            description=data[4],
            price=data[5],
            stock=data[6],
            image_path=data[7],
            product_id=data[0],
        )
