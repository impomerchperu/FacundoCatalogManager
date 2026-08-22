import shutil
from pathlib import Path

import pytest

from database.db_manager import DBManager
from repositories.product_repository import ProductRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DIAGNOSTIC_FILES = (
    PROJECT_ROOT / "data" / "scraping_timing.log",
    PROJECT_ROOT / "data" / "last_scraping_codes.json",
)


@pytest.fixture(scope="session", autouse=True)
def preserve_scraping_diagnostics():
    """Prevent pytest from contaminating the last real scraping diagnostics."""
    backups: dict[Path, Path] = {}
    for source in _DIAGNOSTIC_FILES:
        if not source.exists():
            continue
        backup = source.with_suffix(source.suffix + ".pytest-backup")
        shutil.copy2(source, backup)
        backups[source] = backup

    try:
        yield
    finally:
        for source, backup in backups.items():
            if backup.exists():
                shutil.copy2(backup, source)
                backup.unlink()


@pytest.fixture
def database():
    db = DBManager(":memory:")
    db.initialize_database()
    yield db
    db.close()


@pytest.fixture
def repository(database):
    return ProductRepository(database)
