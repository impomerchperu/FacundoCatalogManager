from services.product_service import ProductService


class ProductController:
    def __init__(self):
        self.service = ProductService()

    def get_products(self):
        return self.service.get_products()

    def create_product(self, product):
        self.service.create_product(product)

    def update_product(self, product):
        self.service.update_product(product)

    def delete_product(self, product_id):
        self.service.delete_product(product_id)

    def search_products(self, text):
        return self.service.search_products(text)

    def get_product_by_id(self, product_id):

        return self.service.get_product_by_id(product_id)
