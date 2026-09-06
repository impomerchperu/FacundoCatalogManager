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


def test_canonical_scraping_factory_does_not_use_legacy_sync_engine():
    source = (
        PROJECT_ROOT / "services" / "scraping" / "scraping_factory.py"
    ).read_text(encoding="utf-8")

    forbidden_imports = (
        "scrapers.sync.sync_engine",
        "repositories.scraping.sync_repository",
    )

    assert not any(token in source for token in forbidden_imports)


def test_canonical_scraping_factory_uses_modern_product_scraping_service():
    source = (
        PROJECT_ROOT / "services" / "scraping" / "scraping_factory.py"
    ).read_text(encoding="utf-8")

    assert "from services.scraping.category_product_scraping_service import" in source
    assert "scrapers.services.category_product_scraping_service" not in source


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


def test_compatibility_package_exports_remain_intentional():
    code = """
from services.scraping import CategoryProductScrapingService

assert CategoryProductScrapingService.__name__ == "CategoryProductScrapingService"

import services.scraping as scraping
assert not hasattr(scraping, "CategoryPaginationService")
assert not hasattr(scraping, "CategoryScrapingService")
assert not hasattr(scraping, "ScrapedProductService")
"""

    subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_full_scraping_service_is_not_eagerly_loaded():
    code = """
import sys
import services.scraping

assert "services.scraping.full_scraping_service" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_scraping_controller_does_not_depend_on_legacy_orchestrator():
    source = (
        PROJECT_ROOT / "controllers" / "scraping_controller.py"
    ).read_text(encoding="utf-8")

    assert "from services.scraping.scraping_factory import ScrapingFactory" in source
    assert "from services.scraping.scraping_session import ScrapingSession" in source
    assert "FullScrapingService" not in source


def test_modern_scraping_services_do_not_import_legacy_service_modules():
    services_dir = PROJECT_ROOT / "services" / "scraping"
    allowed_legacy_files = {
        "__init__.py",
        "full_scraping_service.py",
    }
    forbidden_imports = (
        "services.scraping.category_pagination_service",
        "services.scraping.category_scraping_service",
        "services.scraping.scraped_product_service",
        "services.scraping.full_scraping_service",
    )

    violations = []
    for path in services_dir.glob("*.py"):
        if path.name in allowed_legacy_files:
            continue

        source = path.read_text(encoding="utf-8")
        for token in forbidden_imports:
            if token in source:
                violations.append(f"{path.name}: {token}")

    assert violations == []


def test_modern_category_product_service_does_not_load_legacy_duplicate():
    code = """
import sys
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)

assert CategoryProductScrapingService.__module__ == (
    "services.scraping.category_product_scraping_service"
)
assert "scrapers.services.category_product_scraping_service" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_removed_legacy_parser_modules_stay_absent():
    removed_paths = (
        PROJECT_ROOT / "scrapers" / "parser",
        PROJECT_ROOT / "scrapers" / "product_scraper.py",
    )

    assert all(not path.exists() for path in removed_paths)


def test_production_roots_do_not_import_legacy_scraping_services():
    production_roots = (
        PROJECT_ROOT / "app.py",
        PROJECT_ROOT / "controllers",
        PROJECT_ROOT / "factories",
        PROJECT_ROOT / "gui",
        PROJECT_ROOT / "models",
        PROJECT_ROOT / "repositories",
        PROJECT_ROOT / "services",
        PROJECT_ROOT / "scrapers",
    )
    allowed_paths = {
        Path("services/scraping/full_scraping_service.py"),
    }
    forbidden_imports = (
        "services.scraping.category_pagination_service",
        "services.scraping.category_scraping_service",
        "services.scraping.full_scraping_service",
        "services.scraping.scraped_product_service",
        "scrapers.services.category_product_scraping_service",
        "scrapers.parser",
        "scrapers.product_scraper",
    )

    violations = []
    for root in production_roots:
        paths = [root] if root.is_file() else root.rglob("*.py")
        for path in paths:
            relative_path = path.relative_to(PROJECT_ROOT)
            if relative_path in allowed_paths:
                continue

            source = path.read_text(encoding="utf-8")
            for token in forbidden_imports:
                if token in source:
                    violations.append(f"{relative_path}: {token}")

    assert violations == []
