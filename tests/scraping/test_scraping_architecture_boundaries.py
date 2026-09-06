import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_canonical_scraping_factory_does_not_depend_on_legacy_pipeline():
    source = (
        PROJECT_ROOT / "services" / "scraping" / "scraping_factory.py"
    ).read_text(encoding="utf-8")

    forbidden_imports = (
        "scrapers.parser",
        "scrapers.services",
        "scrapers.factories",
        "services.scraping.category_scraping_service",
        "services.scraping.category_pagination_service",
        "services.scraping.scraped_product_service",
    )

    assert not any(token in source for token in forbidden_imports)


def test_compatibility_factories_delegate_to_canonical_factory():
    factories = (
        PROJECT_ROOT / "factories" / "scraping_factory.py",
        PROJECT_ROOT / "scrapers" / "factories" / "scraping_factory.py",
    )

    for path in factories:
        source = path.read_text(encoding="utf-8")
        assert "services.scraping.scraping_factory" in source
        assert "CanonicalScrapingFactory" in source
        assert "return CanonicalScrapingFactory.create_runner" in source


def test_scraping_package_does_not_eagerly_import_legacy_services():
    code = """
import sys
import services.scraping

legacy_modules = (
    "services.scraping.category_pagination_service",
    "services.scraping.category_scraping_service",
    "services.scraping.scraped_product_service",
)

assert not any(module in sys.modules for module in legacy_modules)
"""

    subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_legacy_services_remain_available_through_public_package_api():
    code = """
from services.scraping import CategoryPaginationService, ScrapedProductService

assert CategoryPaginationService.__name__ == "CategoryPaginationService"
assert ScrapedProductService.__name__ == "ScrapedProductService"
"""

    subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
