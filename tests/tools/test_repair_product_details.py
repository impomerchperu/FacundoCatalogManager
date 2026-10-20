from database.db_manager import DBManager
from models.product import Product
from models.scraping.scraped_product import ScrapedProduct
from repositories.product_repository import ProductRepository
from repositories.scraping.scraped_product_repository import ScrapedProductRepository
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.product_hash_service import ProductHashService
from tools.repair_product_details import (
    apply_detail_repairs,
    audit_incomplete_details,
    plan_product_detail_repairs,
)

PRODUCT_URL = (
    "https://stock.importacionesfacundo.com/producto/producto-prueba/"
)
VALID_DETAIL = "Color: Rojo. Material: ABS. Dimensiones: 10 x 5 cm."


class StaticBrowser:
    def __init__(self, html: str):
        self.html = html
        self.requested_urls: list[str] = []

    def get(self, url: str) -> str:
        self.requested_urls.append(url)
        return self.html


def _product_html(
    code: str = "FB-1700",
    detail: str = VALID_DETAIL,
) -> str:
    return f"""
    <html>
      <body>
        <h1>Producto de prueba</h1>
        <p class="brxe-heading">{code}</p>
        <div class="woocommerce-product-details__short-description">
          {detail}
        </div>
      </body>
    </html>
    """


def _seed_catalog(
    *,
    code: str = "FB-1700",
    description: str = "Detalle comercial antiguo",
    source_url: str = PRODUCT_URL,
) -> tuple[DBManager, ProductRepository]:
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    repository.save(
        Product(
            code=code,
            name="Producto guardado",
            category="Promocionales",
            description=description,
            price=10,
            price_sample=10,
            stock=7,
            image_url="https://stock.importacionesfacundo.com/imagen.jpg",
            image_path="images/FB-1700.jpg",
            image_hash="image-hash",
        )
    )
    if source_url:
        ScrapedProductRepository(db).save(
            ScrapedProduct(
                source="importacionesfacundo",
                url=source_url,
                code=code,
                name="Producto guardado",
                category="Promocionales",
            )
        )
    return db, repository


def test_targeted_detail_repair_preview_does_not_modify_catalog():
    db, repository = _seed_catalog()
    browser = StaticBrowser(_product_html())
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["fb-1700", "FB-1700"],
            browser=browser,
        )

        assert len(plans) == 1
        assert plans[0].status == "would_update"
        assert plans[0].new_description == VALID_DETAIL
        assert plans[0].old_description == "Detalle comercial antiguo"
        assert browser.requested_urls == [PRODUCT_URL]

        stored = repository.get_by_code("FB-1700")
        assert stored is not None
        assert stored.description == "Detalle comercial antiguo"
        assert stored.image_path == "images/FB-1700.jpg"
    finally:
        db.close()


def test_targeted_detail_repair_updates_only_detail_and_content_hash():
    db, repository = _seed_catalog()
    browser = StaticBrowser(_product_html())
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["FB-1700"],
            browser=browser,
        )

        updated = apply_detail_repairs(db, repository, plans)

        assert updated == 1
        assert plans[0].status == "updated"
        stored = repository.get_by_code("FB-1700")
        assert stored is not None
        assert stored.description == VALID_DETAIL
        assert stored.name == "Producto guardado"
        assert stored.category == "Promocionales"
        assert stored.price == 10
        assert stored.price_sample == 10
        assert stored.stock == 7
        assert stored.image_url == (
            "https://stock.importacionesfacundo.com/imagen.jpg"
        )
        assert stored.image_path == "images/FB-1700.jpg"
        assert stored.image_hash == "image-hash"
        assert stored.content_hash == ProductHashService().generate(stored)
    finally:
        db.close()


def test_targeted_detail_repair_rejects_a_page_with_a_different_product_code():
    db, repository = _seed_catalog()
    browser = StaticBrowser(_product_html(code="FB-1701"))
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["FB-1700"],
            browser=browser,
        )

        assert plans[0].status == "skip_code_mismatch"
        assert "FB-1701" in plans[0].reason
        assert apply_detail_repairs(db, repository, plans) == 0
        stored = repository.get_by_code("FB-1700")
        assert stored is not None
        assert stored.description == "Detalle comercial antiguo"
    finally:
        db.close()


def test_targeted_detail_repair_rejects_incomplete_extracted_detail():
    db, repository = _seed_catalog()
    browser = StaticBrowser(_product_html(detail="Material:"))
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["FB-1700"],
            browser=browser,
        )

        assert plans[0].status == "skip_invalid_detail"
        assert "detalle_vacío" in plans[0].reason
        assert apply_detail_repairs(db, repository, plans) == 0
    finally:
        db.close()


def test_targeted_detail_repair_does_not_fetch_urls_from_untrusted_hosts():
    db, repository = _seed_catalog(
        source_url="https://example.com/not-the-product-page/"
    )
    browser = StaticBrowser(_product_html())
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["FB-1700"],
            browser=browser,
        )

        assert plans[0].status == "skip_source_url_not_found"
        assert browser.requested_urls == []
        assert apply_detail_repairs(db, repository, plans) == 0
    finally:
        db.close()


def test_audit_incomplete_details_lists_only_values_rejected_by_shared_policy():
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    repository.save(
        Product(code="FB-1700", name="Sin detalle", description="")
    )
    repository.save(
        Product(
            code="FB-6005",
            name="Texto comercial",
            description="Descripción comercial: artículo práctico.",
        )
    )
    repository.save(
        Product(
            code="FB-6002",
            name="Detalle completo",
            description=VALID_DETAIL,
        )
    )
    try:
        report = audit_incomplete_details(db, repository, limit=10)

        assert report["mode"] == "audit_only"
        assert report["total_incomplete"] == 2
        items = report["items"]
        assert isinstance(items, list)
        assert [item["code"] for item in items] == ["FB-1700", "FB-6005"]
    finally:
        db.close()
