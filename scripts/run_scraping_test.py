from models.scraping.category import Category
from services.scraping.scraping_factory import ScrapingFactory


def main():

    runner = ScrapingFactory.create_runner()

    category = Category(
        name="Jarros Mug",
        url="https://stock.importacionesfacundo.com/categoria-producto/jarros-mug",
    )

    products = runner.run(
        [
            category,
        ]
    )

    print("=" * 80)
    print("PRODUCTOS OBTENIDOS")
    print("=" * 80)

    for product in products:
        print()
        print("Código:", product.code)
        print("Nombre:", product.name)
        print("Categoría:", product.category)
        print("Stock:", product.stock)
        print("Precio muestra:", product.price_sample)
        print("Precio ciento:", product.price_hundred)
        print("Precio millar:", product.price_thousand)
        print("Imagen:", product.image_url)
        print("-" * 80)


if __name__ == "__main__":
    main()
