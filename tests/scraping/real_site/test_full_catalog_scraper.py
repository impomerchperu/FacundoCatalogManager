from collections import Counter
from time import perf_counter

import pytest

from config.scraping_config import STORE_URL
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_service import CategoryService

EXPECTED_CATEGORIES = 24
# The live catalog baseline captured by the project before this coverage pass.
EXPECTED_CATEGORY_OCCURRENCES = 530
EXPECTED_UNIQUE_PRODUCTS = 526
EXPECTED_MULTI_CATEGORY_PRODUCTS = 4
PRODUCTS_PER_PAGE = 25


@pytest.mark.real_site
def test_full_catalog_scraper_real_site():
    """Recorre todo el catálogo con el scraper resiliente usado en producción."""
    started = perf_counter()
    browser = Browser()
    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
    )
    category_service = CategoryService(category_scraper, STORE_URL)
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
    )

    categories = category_service.scrape_all()
    assert len(categories) == EXPECTED_CATEGORIES, categories

    expected_total = sum(
        max(int(category.expected_count or 0), 0)
        for category in categories
    )
    if expected_total != EXPECTED_CATEGORY_OCCURRENCES:
        print("=" * 80)
        print("DESVIACIÓN DEL BASELINE DE APARICIONES")
        print("ESPERADO:", EXPECTED_CATEGORY_OCCURRENCES)
        print("OBTENIDO:", expected_total)
        print("DIFERENCIA:", expected_total - EXPECTED_CATEGORY_OCCURRENCES)
        for index, category in enumerate(categories, start=1):
            print(
                f"[{index:02d}/{len(categories):02d}] "
                f"{category.name}: expected={category.expected_count}"
            )
        print("DURACIÓN DESCUBRIMIENTO:", f"{perf_counter() - started:.2f}s")
        print("=" * 80)
    assert expected_total == EXPECTED_CATEGORY_OCCURRENCES

    products = []
    category_results = []
    errors = []
    for index, category in enumerate(categories, start=1):
        category_started = perf_counter()
        try:
            category_products = collection.scrape_category(category)
        except Exception as error:  # noqa: BLE001
            category_products = []
            errors.append(
                f"{category.name}: {type(error).__name__}: {error}"
            )
        products.extend(category_products)
        found = len(category_products)

        metrics = collection.get_page_metrics().get(category.url, {})
        expected = max(int(category.expected_count or 0), 0)
        required_pages = max(
            (expected + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE,
            1,
        )
        pages_requested = int(metrics.get("pages_requested", 0) or 0)
        pages_loaded = int(metrics.get("pages_loaded", 0) or 0)
        cards_found = int(metrics.get("cards_found", 0) or 0)
        page_error = None
        if pages_requested < required_pages:
            page_error = (
                f"pages_requested={pages_requested} < "
                f"required_pages={required_pages}"
            )
        elif pages_loaded != pages_requested:
            page_error = (
                f"pages_loaded={pages_loaded} != "
                f"pages_requested={pages_requested}"
            )

        category_results.append(
            {
                "category": category.name,
                "expected": expected,
                "found": found,
                "gap": max(expected - found, 0),
                "pages_expected": required_pages,
                "pages_requested": pages_requested,
                "pages_loaded": pages_loaded,
                "cards_found": cards_found,
                "page_error": page_error,
            }
        )
        print(
            f"[{index:02d}/{len(categories):02d}] "
            f"{category.name}: expected={expected} "
            f"found={found} "
            f"pages={pages_loaded}/{required_pages} "
            f"cards={cards_found} "
            f"seconds={perf_counter() - category_started:.2f}"
        )

    codes = [str(product.code).strip().upper() for product in products if product.code]
    missing_codes = [
        index
        for index, product in enumerate(products, start=1)
        if not str(product.code).strip()
    ]
    code_counts = Counter(codes)
    duplicate_codes = sorted(
        code for code, count in code_counts.items() if count > 1
    )
    multi_category_codes = [
        code for code in duplicate_codes if code_counts[code] >= 2
    ]
    without_prices = [
        product.code
        for product in products
        if product.price_sample <= 0
        and product.price_hundred <= 0
        and product.price_thousand <= 0
    ]
    without_images = [
        product.code
        for product in products
        if not product.image_url
    ]

    print("=" * 80)
    print("CATEGORÍAS:", len(categories))
    print("APARICIONES ESPERADAS:", expected_total)
    print("APARICIONES ENCONTRADAS:", len(products))
    print("PRODUCTOS ÚNICOS:", len(code_counts))
    print("PRODUCTOS MULTI-CATEGORÍA:", len(multi_category_codes))
    print("CÓDIGOS SIN CÓDIGO:", len(missing_codes))
    print("DUPLICADOS POR CÓDIGO:", duplicate_codes)
    print("PRODUCTOS SIN PRECIO:", without_prices)
    print("PRODUCTOS SIN IMAGEN:", without_images)
    print("ERRORES DE CATEGORÍA:", errors)
    print("ERRORES DE COBERTURA DE PÁGINAS:", [
        row for row in category_results if row["page_error"]
    ])
    print("DURACIÓN TOTAL:", f"{perf_counter() - started:.2f}s")
    print("=" * 80)

    gaps = [row for row in category_results if row["gap"]]
    page_errors = [row for row in category_results if row["page_error"]]
    assert not errors, errors
    assert not missing_codes, missing_codes[:20]
    assert not gaps, gaps
    assert not page_errors, page_errors
    assert len(products) == EXPECTED_CATEGORY_OCCURRENCES
    assert len(code_counts) == EXPECTED_UNIQUE_PRODUCTS
    assert len(multi_category_codes) == EXPECTED_MULTI_CATEGORY_PRODUCTS
