from dataclasses import dataclass

from database.db_manager import DBManager
from services.catalog_bootstrap_service import CatalogBootstrapService


@dataclass
class FakeResult:
    successful: bool = True

    def success(self) -> bool:
        return self.successful


class FakeController:
    def __init__(self, db: DBManager) -> None:
        self.db = db

    def run_full_scraping(self):
        self.db.execute_query(
            """
            INSERT INTO products (code, name, category)
            VALUES (?, ?, ?)
            """,
            ("BOOT001", "Producto inicial", "General"),
        )
        return FakeResult()


def test_bootstrap_populates_empty_catalog_and_marks_it_initialized(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    service = CatalogBootstrapService(
        db=db,
        controller_factory=lambda: FakeController(db),
    )

    assert service.is_ready() is False

    result = service.bootstrap()

    assert result is not None
    assert result.success() is True
    assert service.product_count() == 1
    assert service.is_initialized() is True
    assert service.is_ready() is True

    db.close()


def test_bootstrap_does_not_scrape_initialized_catalog(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    service = CatalogBootstrapService(
        db=db,
        controller_factory=lambda: (_ for _ in ()).throw(
            AssertionError("No debe ejecutar scraping")
        ),
    )
    service.mark_initialized()
    db.commit()

    assert service.bootstrap() is None
    assert service.product_count() == 0

    db.close()
