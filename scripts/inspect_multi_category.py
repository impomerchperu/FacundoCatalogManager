from collections import defaultdict

from services.scraping.scraping_factory import ScrapingFactory


def main() -> None:
    runner = ScrapingFactory.create_runner()

    category_service = runner.category_service
    scraping_service = runner.scraping_service

    if category_service is None:
        raise RuntimeError("ScrapingRunner no tiene CategoryService configurado.")

    scraper_service = getattr(
        scraping_service,
        "scraper_service",
        None,
    )

    if scraper_service is None:
        raise RuntimeError(
            "El servicio de sincronización no tiene "
            "CategoryProductScrapingService configurado."
        )

    categories = category_service.scrape_all()

    products_by_code: dict[str, set[str]] = defaultdict(set)
    products_by_category: dict[str, int] = {}

    total_appearances = 0

    print("=" * 80)
    print("BUSQUEDA DE PRODUCTOS MULTICATEGORIA")
    print("=" * 80)
    print()

    for index, category in enumerate(categories, start=1):
        print(f"[{index:02d}/{len(categories)}] {category.name}")

        products = scraper_service.scrape_category(
            category.url,
            category.name,
        )

        products_by_category[category.name] = len(products)
        total_appearances += len(products)

        for product in products:
            code = getattr(product, "code", None)

            if code:
                products_by_code[code].add(category.name)

    print()
    print("=" * 80)
    print("RESUMEN POR CATEGORIA")
    print("=" * 80)
    print()

    for category_name, count in products_by_category.items():
        print(f"{category_name}: {count}")

    unique_products = len(products_by_code)

    shared = {
        code: category_names
        for code, category_names in products_by_code.items()
        if len(category_names) > 1
    }

    print()
    print("=" * 80)
    print("RESUMEN GENERAL")
    print("=" * 80)
    print()
    print(f"TOTAL APARICIONES DE PRODUCTOS: {total_appearances}")
    print(f"TOTAL PRODUCTOS UNICOS POR CODIGO: {unique_products}")
    print(f"PRODUCTOS EN MAS DE UNA CATEGORIA: {len(shared)}")

    print()
    print("=" * 80)
    print("PRODUCTOS MULTICATEGORIA")
    print("=" * 80)
    print()

    if not shared:
        print("No se encontraron productos multicategoria.")
        return

    for code, category_names in sorted(shared.items()):
        print(code)

        for category_name in sorted(category_names):
            print(f"    - {category_name}")

        print()


if __name__ == "__main__":
    main()
