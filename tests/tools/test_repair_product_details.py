import json

from bs4 import BeautifulSoup

from database.db_manager import DBManager
from models.product import Product
from models.scraping.category import Category
from models.scraping.scraped_product import ScrapedProduct
from repositories.product_repository import ProductRepository
from repositories.scraping.scraped_product_repository import ScrapedProductRepository
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.product_hash_service import ProductHashService
from tools.repair_product_details import (
    _audit_live_category_cards,
    _card_detail_field_is_identified,
    _emit_json_report,
    _plan_category_card_detail,
    _plan_from_detail_candidate,
    _resolve_category_batches,
    apply_detail_repairs,
    audit_incomplete_details,
    audit_source_details,
    plan_product_detail_repairs,
)

PRODUCT_URL = (
    "https://stock.importacionesfacundo.com/producto/producto-prueba/"
)
VALID_DETAIL = "Material: ABS. Dimensiones: 10 x 5 cm."


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


def test_category_detail_field_is_identified_even_when_empty():
    empty_detail_card = BeautifulSoup(
        '<article><div class="text-content"></div></article>',
        "lxml",
    ).article
    assert empty_detail_card is not None

    assert _card_detail_field_is_identified(empty_detail_card, "") is True


def test_complete_category_card_detail_is_authoritative_over_product_page():
    db, repository = _seed_catalog(description="Detalle guardado anterior")
    browser = StaticBrowser(_product_html(detail="Material: PLÁSTICO. Dimensiones: 99 x 99 cm."))
    product = repository.get_by_code("FB-1700")
    card = BeautifulSoup(
        '<article><div class="text-content">'
        "Material: ABS. Dimensiones: 10 x 5 cm. Presentación: Individual."
        "</div></article>",
        "lxml",
    ).article
    assert product is not None
    assert card is not None
    card_description = (
        "Material: ABS. Dimensiones: 10 x 5 cm. Presentación: Individual."
    )
    try:
        plan = _plan_category_card_detail(
            db,
            repository,
            product,
            card,
            card_description,
            source_url=PRODUCT_URL,
            category_name="Promocionales",
            browser=browser,
        )

        assert plan.status == "would_update"
        assert plan.new_description == card_description
        assert "tarjeta de categoría" in plan.reason
        assert browser.requested_urls == []
    finally:
        db.close()


def test_category_card_fallback_detail_survives_excluded_text_content_block():
    db, repository = _seed_catalog(description="Detalle anterior")
    browser = StaticBrowser(
        _product_html(detail="Material: PLÁSTICO. Dimensiones: 99 x 99 cm.")
    )
    product = repository.get_by_code("FB-1700")
    card = BeautifulSoup(
        """
        <article>
          <div id="tab-description" role="tabpanel">
            <div class="text-content"></div>
          </div>
          <div class="brxe-text-basic">
            <p>Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)</p>
            <p>Material: Bambú y ABS</p>
            <p>Funciones: 7 funciones (cinta métrica de 3 m, destornillador con puntas planas, philips y allen, nivel integrado)</p>
            <p>Accesorios: 5 piezas incluidas</p>
            <p>Peso: 108 gr (Aprox)</p>
            <p>Presentación: Individual, caja diseño kraft</p>
          </div>
        </article>
        """,
        "lxml",
    ).article
    assert product is not None
    assert card is not None
    try:
        card_description = CategoryProductExtractor()._description(card)
        assert "Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)" in card_description
        assert "Material: Bambú y ABS" in card_description
        assert "Accesorios: 5 piezas incluidas" in card_description
        assert _card_detail_field_is_identified(card, "") is True

        plan = _plan_category_card_detail(
            db,
            repository,
            product,
            card,
            card_description,
            source_url=PRODUCT_URL,
            category_name="Artículos de Escritorio",
            browser=browser,
        )

        assert plan.status == "would_update"
        assert plan.new_description == card_description
        assert "tarjeta de categoría" in plan.reason
        assert browser.requested_urls == []
    finally:
        db.close()


def test_empty_text_content_shell_does_not_clear_visible_multiblock_category_detail():
    db, repository = _seed_catalog(description="Detalle comercial antiguo")
    browser = StaticBrowser(
        _product_html(detail="Material: PLÁSTICO. Dimensiones: 99 x 99 cm.")
    )
    product = repository.get_by_code("FB-1700")
    card = BeautifulSoup(
        """
        <article>
          <div class="text-content"></div>
          <div class="brxe-text-basic">
            <p>Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)</p>
            <p>Material: Bambú y ABS</p>
            <p>Funciones: 7 funciones (cinta métrica de 3 m, destornillador con puntas planas, philips y allen, nivel integrado)</p>
            <p>Accesorios: 5 piezas incluidas</p>
            <p>Peso: 108 gr (Aprox)</p>
            <p>Color: Negro con…</p>
            <p>Presentación: Individual, caja diseño kraft</p>
          </div>
        </article>
        """,
        "lxml",
    ).article
    assert product is not None
    assert card is not None

    try:
        card_description = CategoryProductExtractor()._description(card)
        assert "Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)" in card_description
        assert "Presentación: Individual, caja diseño kraft" in card_description
        assert "Color:" not in card_description

        plan = _plan_category_card_detail(
            db,
            repository,
            product,
            card,
            card_description,
            source_url=PRODUCT_URL,
            category_name="Artículos de Escritorio",
            browser=browser,
        )

        assert plan.status == "would_update"
        assert plan.new_description == card_description
        assert "tarjeta de categoría" in plan.reason
        assert browser.requested_urls == []
    finally:
        db.close()


def test_color_only_category_block_uses_visible_sibling_detail_fields():
    db, repository = _seed_catalog(description="Detalle comercial antiguo")
    browser = StaticBrowser(
        _product_html(detail="Material: PLÁSTICO. Dimensiones: 99 x 99 cm.")
    )
    product = repository.get_by_code("FB-1700")
    card = BeautifulSoup(
        """
        <article>
          <div class="text-content">Color: Negro con…</div>
          <div class="brxe-text-basic">
            <p>Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)</p>
            <p>Material: Bambú y ABS</p>
            <p>Funciones: 7 funciones (cinta métrica de 3 m, destornillador con puntas planas, philips y allen, nivel integrado)</p>
            <p>Accesorios: 5 piezas incluidas</p>
            <p>Peso: 108 gr (Aprox)</p>
            <p>Presentación: Individual, caja diseño kraft</p>
          </div>
        </article>
        """,
        "lxml",
    ).article
    assert product is not None
    assert card is not None

    try:
        card_description = CategoryProductExtractor()._description(card)
        assert "Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)" in card_description
        assert "Presentación: Individual, caja diseño kraft" in card_description
        assert "Color:" not in card_description

        plan = _plan_category_card_detail(
            db,
            repository,
            product,
            card,
            card_description,
            source_url=PRODUCT_URL,
            category_name="Artículos de Escritorio",
            browser=browser,
        )

        assert plan.status == "would_update"
        assert plan.new_description == card_description
        assert "tarjeta de categoría" in plan.reason
        assert browser.requested_urls == []
    finally:
        db.close()


def test_repair_reextracts_visible_card_detail_when_scraped_description_is_empty():
    db, repository = _seed_catalog(description="Detalle comercial antiguo")
    browser = StaticBrowser(
        _product_html(detail="Material: PLÁSTICO. Dimensiones: 99 x 99 cm.")
    )
    product = repository.get_by_code("FB-1700")
    card = BeautifulSoup(
        """
        <article>
          <div class="text-content">Color: Negro con…</div>
          <div class="brxe-text-basic">
            <p>Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)</p>
            <p>Material: Bambú y ABS</p>
            <p>Funciones: 7 funciones (cinta métrica de 3 m, destornillador con puntas planas, philips y allen, nivel integrado)</p>
            <p>Accesorios: 5 piezas incluidas</p>
            <p>Peso: 108 gr (Aprox)</p>
            <p>Presentación: Individual, caja diseño kraft</p>
          </div>
        </article>
        """,
        "lxml",
    ).article
    assert product is not None
    assert card is not None

    try:
        # Mirrors the live report: the collection result says blank, but the
        # raw category card still contains the source Detail in sibling blocks.
        plan = _plan_category_card_detail(
            db,
            repository,
            product,
            card,
            "",
            source_url=PRODUCT_URL,
            category_name="Artículos de Escritorio",
            browser=browser,
        )

        assert plan.status == "would_update"
        assert "Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)" in plan.new_description
        assert "Material: Bambú y ABS" in plan.new_description
        assert "Funciones: 7 funciones" in plan.new_description
        assert "Accesorios: 5 piezas incluidas" in plan.new_description
        assert "Peso: 108 gr (Aprox)" in plan.new_description
        assert "Presentación: Individual, caja diseño kraft" in plan.new_description
        assert "Color:" not in plan.new_description
        assert "tarjeta de categoría" in plan.reason
        assert browser.requested_urls == []
    finally:
        db.close()


def test_empty_identified_category_detail_is_not_supplemented_from_product_page():
    db, repository = _seed_catalog(description=VALID_DETAIL)
    browser = StaticBrowser(_product_html(detail="Material: PLÁSTICO. Dimensiones: 99 x 99 cm."))
    product = repository.get_by_code("FB-1700")
    card = BeautifulSoup(
        '<article><div class="text-content"></div></article>',
        "lxml",
    ).article
    assert product is not None
    assert card is not None
    try:
        plan = _plan_category_card_detail(
            db,
            repository,
            product,
            card,
            "",
            source_url=PRODUCT_URL,
            category_name="Promocionales",
            browser=browser,
        )

        assert plan.status == "would_update"
        assert plan.new_description == ""
        assert "identificado y vacío" in plan.reason
        assert browser.requested_urls == []
    finally:
        db.close()


def test_truncated_category_detail_uses_complete_product_page_field():
    db, repository = _seed_catalog(description="Material: ABS. Dimensiones: 8 x 4 cm.")
    browser = StaticBrowser(_product_html(detail=VALID_DETAIL))
    product = repository.get_by_code("FB-1700")
    card = BeautifulSoup(
        '<article><div class="text-content">'
        "Material: ABS. Dimensiones: 10 x 5 cm…"
        "</div></article>",
        "lxml",
    ).article
    assert product is not None
    assert card is not None
    try:
        plan = _plan_category_card_detail(
            db,
            repository,
            product,
            card,
            "Material: ABS. Dimensiones: 10 x 5 cm…",
            source_url=PRODUCT_URL,
            category_name="Promocionales",
            browser=browser,
        )

        assert plan.status == "would_update"
        assert plan.new_description == VALID_DETAIL
        assert browser.requested_urls == [PRODUCT_URL]
    finally:
        db.close()


def test_category_audit_compares_live_card_field_not_product_page_field():
    db, repository = _seed_catalog(description=VALID_DETAIL)
    product = repository.get_by_code("FB-1700")
    assert product is not None
    card_description = "Material: ABS. Dimensiones: 12 x 6 cm."
    card = BeautifulSoup(
        f'<article><div class="text-content">{card_description}</div></article>',
        "lxml",
    ).article
    assert card is not None
    source_product = ScrapedProduct(
        code="FB-1700",
        name="Producto guardado",
        category="Promocionales",
        url=PRODUCT_URL,
        description=card_description,
    )

    class StaticCollectionScraper:
        def collect_category(self, category):
            assert category.name == "Promocionales"
            return [(card, "https://stock.importacionesfacundo.com/categoria/", source_product)]

    browser = StaticBrowser(
        _product_html(detail="Material: PLÁSTICO. Dimensiones: 99 x 99 cm.")
    )
    try:
        report, coverage_verified = _audit_live_category_cards(
            db,
            repository,
            Category(
                name="Promocionales",
                url="https://stock.importacionesfacundo.com/categoria/promocionales/",
                expected_count=1,
            ),
            [product],
            browser=browser,
            collection_scraper=StaticCollectionScraper(),
        )

        assert coverage_verified is True
        assert report["candidate_differences"] == 1
        plan = report["items"][0]
        assert plan["new_description"] == card_description
        assert plan["reason"].find("tarjeta de categoría") >= 0
        assert browser.requested_urls == []
    finally:
        db.close()


def test_category_detail_preview_ignores_boundary_only_changes():
    db, repository = _seed_catalog(
        description="Material: ABS. Dimensiones: 10 x 5 cm."
    )
    product = repository.get_by_code("FB-1700")
    assert product is not None
    candidate = "Material: ABS.\nDimensiones: 10 x 5 cm."

    try:
        plan = _plan_from_detail_candidate(
            product,
            PRODUCT_URL,
            candidate,
            reason="Detalle live de tarjeta",
        )

        assert plan.status == "unchanged"
        assert plan.new_description == candidate
    finally:
        db.close()


def test_category_batches_resolve_canonical_names_and_multi_category_products():
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    repository.save(
        Product(
            code="FB-1700",
            name="Producto en dos categorías",
            category="Bolsas / Mochilas, Cocina, Mesa y Hogar",
            description=VALID_DETAIL,
        )
    )
    repository.save(
        Product(
            code="FB-1701",
            name="Producto solo en bolsas",
            category="Bolsas / Mochilas",
            description=VALID_DETAIL,
        )
    )
    try:
        batches = _resolve_category_batches(
            repository,
            ["Cocina, Mesa y Hogar", "Bolsas / Mochilas"],
        )

        assert [name for name, _ in batches] == [
            "Cocina, Mesa y Hogar",
            "Bolsas / Mochilas",
        ]
        assert [product.code for product in batches[0][1]] == ["FB-1700"]
        assert {product.code for product in batches[1][1]} == {
            "FB-1700",
            "FB-1701",
        }
    finally:
        db.close()


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


def test_targeted_detail_repair_preserves_unlabelled_source_field_boundaries():
    flattened_detail = (
        "Tipo de encuadernado: Espiral simple (tipo coil) "
        "Hasta 12 hojas (70 g/m²) por pasada "
        "Capacidad de encuadernado: Hasta 450 hojas"
    )
    db, repository = _seed_catalog(
        code="FB-1902",
        description=flattened_detail,
    )
    html = """
    <html><body>
      <p class="brxe-heading">FB-1902</p>
      <div id="brxe-jhzpri">
        <ul>
          <li>Tipo de encuadernado: Espiral simple (tipo coil)</li>
          <li>Hasta 12 hojas (70 g/m²) por pasada</li>
          <li>Capacidad de encuadernado: Hasta 450 hojas</li>
        </ul>
      </div>
    </body></html>
    """
    browser = StaticBrowser(html)
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["FB-1902"],
            browser=browser,
        )

        assert len(plans) == 1
        assert plans[0].status == "would_update"
        assert plans[0].new_description.splitlines() == [
            "Tipo de encuadernado: Espiral simple (tipo coil)",
            "Hasta 12 hojas (70 g/m²) por pasada",
            "Capacidad de encuadernado: Hasta 450 hojas",
        ]
        assert apply_detail_repairs(db, repository, plans) == 1
        stored = repository.get_by_code("FB-1902")
        assert stored is not None
        assert stored.description.splitlines() == plans[0].new_description.splitlines()
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
        assert "detalle_incompleto_o_truncado" in plans[0].reason
        assert apply_detail_repairs(db, repository, plans) == 0
    finally:
        db.close()


def test_targeted_detail_repair_removes_incomplete_trailing_dimension_field():
    detail = (
        "Marca: Bright Office\n"
        "Modelo: 230\n"
        "Dimensiones del producto: 410 \u00d7 208 \u00d7"
    )
    db, repository = _seed_catalog(description=detail)
    html = """
    <html><body>
      <p class="brxe-heading">FB-1700</p>
      <div id="brxe-jhzpri">
        <ul>
          <li>Marca: Bright Office</li>
          <li>Modelo: 230</li>
          <li>Dimensiones del producto: 410 \u00d7 208 \u00d7</li>
        </ul>
      </div>
    </body></html>
    """
    browser = StaticBrowser(html)
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["FB-1700"],
            browser=browser,
        )

        expected = "Marca: Bright Office\nModelo: 230"
        assert plans[0].status == "would_update"
        assert plans[0].new_description == expected
        assert "Dimensiones del producto" not in plans[0].new_description
        assert apply_detail_repairs(db, repository, plans) == 1

        stored = repository.get_by_code("FB-1700")
        assert stored is not None
        assert stored.description == expected
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
        assert report["total_incomplete"] == 0
        items = report["items"]
        assert isinstance(items, list)
        assert items == []
    finally:
        db.close()


def test_targeted_detail_repair_accepts_visible_summary_prose_and_removes_color():
    detail = (
        "Descripción: Cinta térmica para proyectos de sublimación. "
        "Color: Marrón. Resiste altas temperaturas y mantiene el diseño fijo."
    )
    expected = (
        "Descripción: Cinta térmica para proyectos de sublimación. "
        "Resiste altas temperaturas y mantiene el diseño fijo."
    )
    db, repository = _seed_catalog(description="")
    browser = StaticBrowser(_product_html(detail=detail))
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["FB-1700"],
            browser=browser,
        )
        assert plans[0].status == "would_update"
        assert plans[0].new_description == expected
    finally:
        db.close()


def test_targeted_detail_repair_resolves_sku_without_hyphen():
    db, repository = _seed_catalog(code="TB-5050", description="")
    browser = StaticBrowser(_product_html(code="TB-5050"))
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["TB5050"],
            browser=browser,
        )
        assert len(plans) == 1
        assert plans[0].code == "TB-5050"
        assert plans[0].status == "would_update"
        assert browser.requested_urls == [PRODUCT_URL]
    finally:
        db.close()


def test_authoritative_empty_detail_is_preserved_without_fallback():
    db, repository = _seed_catalog(code="FB-2114", description="Detalle comercial antiguo")
    html = """
    <html><body>
      <h1>Producto de prueba</h1>
      <p class="brxe-heading">FB-2114</p>
      <div id="brxe-jhzpri">
        <h3>Producto de prueba</h3>
        <p></p>
      </div>
      <div class="text-content">
        Este texto pertenece a otra sección y no debe sustituir a Detalle.
      </div>
    </body></html>
    """
    browser = StaticBrowser(html)
    try:
        plans = plan_product_detail_repairs(
            db,
            repository,
            ["FB-2114"],
            browser=browser,
        )

        assert len(plans) == 1
        assert plans[0].status == "would_update"
        assert plans[0].new_description == ""
        stored = repository.get_by_code("FB-2114")
        assert stored is not None
        assert stored.description == "Detalle comercial antiguo"

        assert apply_detail_repairs(db, repository, plans) == 1
        stored = repository.get_by_code("FB-2114")
        assert stored is not None
        assert stored.description == ""
    finally:
        db.close()


def test_authoritative_marketing_copy_is_valid_detail_content():
    detail = (
        "Amplía tus opciones de estilo con nuestro Gorro Sublimable. "
        "Este versátil gorro te permite personalizarlo con tus diseños, "
        "imágenes o logotipos favoritos, lo que lo convierte en una excelente "
        "elección para destacar tu individualidad o promocionar tu marca."
    )
    html = f"""
    <html><body>
      <h1>Gorro Sublimable</h1>
      <p class="brxe-heading">HL-3000</p>
      <div id="brxe-jhzpri"><p>{detail}</p></div>
    </body></html>
    """
    extracted = ProductExtractor().extract(BeautifulSoup(html, "lxml"))
    assert extracted["description"] == detail


def test_audit_source_details_checks_catalog_without_modifying_products():
    db, repository = _seed_catalog(description="")
    browser = StaticBrowser(_product_html(detail=VALID_DETAIL))
    try:
        progress_events = []
        report = audit_source_details(
            db,
            repository,
            browser=browser,
            workers=2,
            progress=lambda completed, total, plan: progress_events.append(
                (completed, total, plan.code, plan.status)
            ),
        )

        assert progress_events == [(1, 1, "FB-1700", "would_update")]
        assert report["mode"] == "source_audit_only"
        assert report["catalog_total"] == 1
        assert report["source_fields_compared"] == 1
        assert report["candidate_differences"] == 1
        assert report["status_counts"] == {"would_update": 1}
        assert browser.requested_urls == [PRODUCT_URL]

        stored = repository.get_by_code("FB-1700")
        assert stored is not None
        assert stored.description == ""
    finally:
        db.close()


def test_json_report_writes_full_records_and_prints_summary(tmp_path, capsys):
    report = {
        "mode": "source_audit_only",
        "catalog_total": 1,
        "items": [
            {
                "code": "FB-1700",
                "old_description": "",
                "new_description": "Prueba",
            },
        ],
    }
    output = tmp_path / "reports" / "detail_audit.json"

    _emit_json_report(report, output)

    saved = json.loads(output.read_text(encoding="utf-8"))
    console = json.loads(capsys.readouterr().out)
    assert saved == report
    assert console["items_saved"] == 1
    assert console["report_file"] == str(output.resolve())
    assert "items" not in console
