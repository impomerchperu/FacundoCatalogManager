from models.scraping.category import Category
from services.scraping.scraping_factory import ScrapingFactory


def print_sync_result(sync_result):
    """
    Muestra métricas de sincronización.
    """

    if sync_result is None:
        print(
            "No existe resultado de sincronización."
        )
        return

    print()
    print("=" * 80)
    print("RESULTADO SINCRONIZACIÓN")
    print("=" * 80)

    print(
        "Procesados:",
        sync_result.processed,
    )

    print(
        "Creados:",
        sync_result.created,
    )

    print(
        "Actualizados:",
        sync_result.updated,
    )

    print(
        "Sin cambios:",
        sync_result.unchanged,
    )

    print(
        "Finalizado:",
        sync_result.finished_at,
    )


def print_products(products):
    """
    Muestra productos sincronizados.
    """

    print()
    print("=" * 80)
    print("PRODUCTOS SINCRONIZADOS")
    print("=" * 80)

    for product in products:

        print()

        print(
            "Código:",
            product.code,
        )

        print(
            "Nombre:",
            product.name,
        )

        print(
            "Categoría:",
            product.category,
        )

        print(
            "Stock:",
            product.stock,
        )

        print(
            "Precio muestra:",
            product.price_sample,
        )

        print(
            "Precio ciento:",
            product.price_hundred,
        )

        print(
            "Precio millar:",
            product.price_thousand,
        )

        print(
            "Imagen:",
            product.image_url,
        )

        print(
            "Archivo:",
            product.image_path,
        )

        print(
            "Hash:",
            product.content_hash,
        )

        print(
            "-" * 80
        )


def main():

    runner = ScrapingFactory.create_runner()

    category = Category(
        name="Jarros Mug",
        url=(
            "https://stock.importacionesfacundo.com/"
            "categoria-producto/jarros-mug"
        ),
    )

    products = runner.run(
        [
            category,
        ]
    )

    print_sync_result(
        runner.scraping_service.last_sync_result
    )

    print_products(
        products
    )


if __name__ == "__main__":
    main()
