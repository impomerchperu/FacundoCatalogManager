from controllers.product_controller import ProductController


class ApplicationFactory:
    """
    Punto central de construcción de los componentes
    principales de la aplicación.
    """

    @staticmethod
    def create_product_controller() -> ProductController:
        return ProductController()
