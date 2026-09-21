from __future__ import annotations

import sys

from config.scraping_config import BASE_URL
from factories.scraping_factory import ScrapingFactory
from models.scraping.category import Category
from services.scraping.scraping_session import ScrapingSession

CATEGORY_NAME = "Bolsas / Mochilas"
CATEGORY_URL = f"{BASE_URL}/categoria-producto/bolsas-mochilas/"


def main() -> int:
    runner = ScrapingFactory.create_runner()
    session = ScrapingSession(
        runner,
        history_repository=runner.history_repository,
        catalog_repository=runner.catalog_repository,
    )

    try:
        result = session.execute(
            [
                Category(
                    name=CATEGORY_NAME,
                    url=CATEGORY_URL,
                )
            ]
        )

        print("=" * 80)
        print("APLICACIÓN DIRIGIDA DE STOCK POR COLOR")
        print("=" * 80)
        print("CATEGORÍA:", CATEGORY_NAME)
        print("ESTADO:", result.status())
        print("PRODUCTOS ENCONTRADOS:", result.products_found)
        print("PRODUCTOS ÚNICOS:", result.products_unique)
        print("CREADOS:", result.created)
        print("ACTUALIZADOS:", result.updated)
        print("SIN CAMBIOS:", result.unchanged)
        print("HISTORIAL ID:", result.history_id)

        color_products = [
            product
            for product in result.products
            if getattr(product, "color_stock", None)
            and len(product.color_stock) >= 2
            and any(int(stock) > 0 for stock in product.color_stock.values())
        ]

        print("PRODUCTOS CON STOCK POR COLOR:", len(color_products))
        for product in color_products[:10]:
            print(
                product.code,
                "|",
                product.name,
                "| STOCK=",
                product.stock,
                "|",
                product.color_stock,
            )

        if result.errors:
            print("ERRORES:")
            for error in result.errors:
                print("-", error)

        print("=" * 80)
        return 0 if result.success() and color_products else 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
