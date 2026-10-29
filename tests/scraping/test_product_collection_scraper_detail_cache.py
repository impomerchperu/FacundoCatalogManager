from models.scraping.category import Category
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_extractor import ProductExtractor


class SharedProductCategoryScraper:
    def __init__(self) -> None:
        self.detail_requests: list[str] = []
        self.html_override: str | None = None
        self.detail_html_override: str | None = None

    def get_category_pages(self, url: str) -> list[str]:
        return [url]

    def get_html(self, url: str) -> str:
        if "/producto/" in url:
            self.detail_requests.append(url)
            if self.detail_html_override is not None:
                return self.detail_html_override
            return """
            <html>
                <h1>Producto compartido</h1>
                <p class="brxe-heading">FB-9999</p>
                <div>Colores: Rojo</div>
            </html>
            """

        if self.html_override is not None:
            return self.html_override

        return """
        <html>
            <article>
                <a href="/producto/producto-compartido/">
                    <h2 class="brxe-f31760">Producto compartido</h2>
                </a>
                <p class="brxe-a26f34">FB-9999</p>
                <div class="variaciones-producto"><p>10</p></div>
            </article>
        </html>
        """


def test_detail_cache_reuses_product_code_across_categories():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    first = scraper.scrape_category(
        Category(name="Jarros", url="https://example.com/jarros/")
    )
    second = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(first) == 1
    assert len(second) == 1
    assert len(category_scraper.detail_requests) == 1

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 1
    assert metrics["detail_cache_hits"] == 1
    assert metrics["detail_cache_size"] == 1

    assert first[0].category == "Jarros"
    assert second[0].category == "Promocionales"


def test_detail_cache_is_cleared_between_full_runs():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    scraper.scrape_category(
        Category(name="Jarros", url="https://example.com/jarros/")
    )
    assert len(category_scraper.detail_requests) == 1

    scraper.reset_detail_metrics()
    scraper.scrape_category(
        Category(name="Jarros", url="https://example.com/jarros/")
    )

    assert len(category_scraper.detail_requests) == 2
    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 1
    assert metrics["detail_cache_hits"] == 0
    assert metrics["detail_cache_size"] == 1


def test_complete_card_color_stock_requests_detail_when_prices_are_missing():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-con-colores/">
                <h2 class="brxe-f31760">Producto con colores</h2>
            </a>
            <p class="brxe-a26f34">FB-1234</p>
            <div class="variaciones-producto">
                <span data-color="Rojo">Rojo</span>
                <span data-color="Azul">Azul</span>
                <p>Rojo: 10</p>
                <p>Azul: 20</p>
            </div>
        </article>
    </html>
    """

    category_scraper.html_override = html
    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert category_scraper.detail_requests == [
        "https://example.com/producto/producto-con-colores/"
    ]
    assert result[0].url == "https://example.com/producto/producto-con-colores/"
    assert result[0].color_stock == {"Rojo": 10, "Azul": 20}
    assert result[0].stock == 30

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 1
    assert metrics["detail_skipped"] == 0
    assert metrics["detail_reason_counts"] == {
        "requested_multiple_labeled_stock": 1,
    }


def test_generic_card_text_is_not_detail_and_description_tab_is_excluded():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/producto-completo/">
                <img src="https://example.com/Logo-Facundo-2026.webp">
                <h2 class="brxe-f31760">Producto completo</h2>
            </a>
            <p class="brxe-a26f34">FB-1235</p>
            <div class="text-content">Descripción promocional general.</div>
            <div class="variaciones-producto"><p>152</p></div>
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Producto completo</h1>
        <p class="brxe-heading">FB-1235</p>
        <div id="tab-description" class="woocommerce-Tabs-panel">
            Material: ABS. Peso neto por caja: 5.5 Kg.
            Peso bruto por caja: 6.25 Kg.
        </div>
        <img class="woocommerce-product-gallery" src="https://example.com/producto.jpg">
        <div class="content-precio">
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </div>
        Stock Disponible 152
    </html>
    """
    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert category_scraper.detail_requests == [
        "https://example.com/producto/producto-completo/"
    ]
    assert result[0].url == "https://example.com/producto/producto-completo/"
    assert result[0].stock == 152
    assert result[0].description == ""

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 1
    assert metrics["detail_skipped"] == 0


def test_detail_reason_metrics_identify_missing_card_data():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-incompleto/">
                <h2 class="brxe-f31760">Producto incompleto</h2>
            </a>
            <p class="brxe-a26f34">FB-1236</p>
            <div class="variaciones-producto"><p>10</p></div>
        </article>
    </html>
    """

    category_scraper.html_override = html
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 1
    assert metrics["detail_reason_counts"] == {
        "requested_missing_fields": 1,
        "requested_missing_description": 1,
        "requested_missing_image_url": 1,
    }


def test_detail_reason_metrics_classify_labeled_multiple_stock():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-colores-incompleto/">
                <h2 class="brxe-f31760">Producto con colores</h2>
            </a>
            <p class="brxe-a26f34">FB-1237</p>
            <div class="variaciones-producto">
                <p>Rojo: 10</p>
                <p>Azul: 20</p>
            </div>
        </article>
    </html>
    """

    category_scraper.html_override = html
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_reason_counts"] == {
        "requested_multiple_labeled_stock": 1,
    }


def test_detail_reason_metrics_classify_multiple_numeric_stock():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-varios-stocks/">
                <h2 class="brxe-f31760">Producto con varios stocks</h2>
            </a>
            <p class="brxe-a26f34">FB-1238</p>
            <div class="variaciones-producto">
                <p>10</p>
                <p>20</p>
            </div>
        </article>
    </html>
    """

    category_scraper.html_override = html
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_reason_counts"] == {
        "requested_multiple_numeric_stock": 1,
    }


def test_detail_reason_metrics_classify_missing_stock():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-sin-stock/">
                <h2 class="brxe-f31760">Producto sin stock visible</h2>
            </a>
            <p class="brxe-a26f34">FB-1239</p>
        </article>
    </html>
    """

    category_scraper.html_override = html
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_reason_counts"] == {
        "requested_missing_stock": 1,
    }


def test_detail_enrichment_merges_missing_fields_and_prices():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/producto-detalle/">
                <h2 class="brxe-f31760">Producto detalle</h2>
            </a>
            <p class="brxe-a26f34">FB-1240</p>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Producto detalle completo</h1>
        <p class="brxe-heading">FB-1240</p>
        <div class="woocommerce-product-details__short-description">
            Material: ABS. Dimensiones: 10 x 5 cm. Certificado SGS
        </div>
        <img class="woocommerce-product-gallery" src="producto-detalle.jpg">
        <div class="content-precio">
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </div>
        Stock Disponible 33
    </html>
    """

    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert result[0].code == "FB-1240"
    assert result[0].description == (
        "Material: ABS. Dimensiones: 10 x 5 cm. Certificado SGS"
    )
    assert result[0].price == 8.0
    assert result[0].price_sample == 8.0
    assert result[0].price_hundred == 700.0
    assert result[0].price_thousand == 6500.0
    assert result[0].stock == 33
    assert result[0].url == "https://example.com/producto/producto-detalle/"


def test_category_description_wins_when_it_has_more_explicit_attributes():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/producto-mas-atributos/">
                <img src="https://example.com/Logo-Facundo-2026.webp">
                <h2 class="brxe-f31760">Producto con atributos</h2>
            </a>
            <p class="brxe-a26f34">FB-4009</p>
            <div class="text-content">
                Color: Blanco. Material: Poliuretano.
                Peso neto por caja: 5.5 Kg.
            </div>
            <div class="variaciones-producto"><p>5</p></div>
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Producto con atributos</h1>
        <p class="brxe-heading">FB-4009</p>
        <div id="tab-description" class="woocommerce-Tabs-panel">
            Descripción promocional general.
        </div>
        <img class="woocommerce-product-gallery"
             src="https://example.com/producto-real.jpg">
        <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
        <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        Stock Disponible 5
    </html>
    """

    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert category_scraper.detail_requests == [
        "https://example.com/producto/producto-mas-atributos/"
    ]
    assert result[0].description == (
        "Material: Poliuretano. Peso neto por caja: 5.5 Kg."
    )


def test_fb4047_truncated_card_uses_visible_summary_and_ignores_tabs():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/muneco-antiestres/">
                <img src="https://example.com/fb-4047.webp">
                <h2 class="brxe-f31760">Producto de ejemplo</h2>
            </a>
            <p class="brxe-a26f34">FB-4047</p>
            <div class="text-content">
                Color: Amarillo, Blanco. Material: Poliuretano.
                Dimensiones: 55*55*100mm. Peso Unitario: 24 G.
                Uso Recomendado: Antiestrés, Promocional.
                Empaque Individual: Bolsa de polietileno.
                Cantidad Por Caja: 250 Pza. Dimensiones Caja: 60*33*32cm.
                Cubicaje por Caja: 0.0634 m³/CBM Peso neto por caja: 7.5 Kg.
                Peso brut…
            </div>
            <div class="variaciones-producto"><p>10</p></div>
            <div class="content-precio">
                <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
            </div>
            <div class="content-precio">
                <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
            </div>
            <div class="content-precio">
                <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
            </div>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Producto de ejemplo</h1>
        <p class="brxe-heading">FB-4047</p>
        <div class="woocommerce-product-details__short-description">
            Color: Amarillo, Blanco. Material: Poliuretano.
            Dimensiones: 55*55*100mm. Peso Unitario: 24 G.
            Uso Recomendado: Antiestrés, Promocional.
            Empaque Individual: Bolsa de polietileno.
            Cantidad Por Caja: 250 Pza. Dimensiones Caja: 60*33*32cm.
            Cubicaje por Caja: 0.0634 m³/CBM Peso neto por caja: 7.5 Kg.
            Peso bruto por caja: 8.5 Kg. Leer Menos Certificado SGS
        </div>
        <div id="tab-description" class="woocommerce-Tabs-panel--description">
            Descripción comercial: Material de cartón, no es el Detalle.
        </div>
        <div id="tab-additional_information">
            Información adicional: dato no autorizado para Detalle.
        </div>
        <div id="tab-reviews">
            Valoraciones: reseñas no autorizadas para Detalle.
        </div>
        <img class="woocommerce-product-gallery"
             src="https://example.com/fb-4047-product.webp">
        <div class="content-precio">
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </div>
        Stock Disponible 10
    </html>
    """

    result = scraper.scrape_category(
        Category(
            name="Artículos Antiestrés",
            url="https://example.com/articulos-antiestres/",
        )
    )

    assert len(result) == 1
    assert result[0].code == "FB-4047"
    assert result[0].name == "Producto de ejemplo"
    assert result[0].category == "Artículos Antiestrés"
    assert result[0].description == (
        "Material: Poliuretano. Dimensiones: 55*55*100mm. "
        "Peso Unitario: 24 G. Uso Recomendado: Antiestrés, Promocional. "
        "Empaque Individual: Bolsa de polietileno. Cantidad Por Caja: 250 Pza. "
        "Dimensiones Caja: 60*33*32cm. Cubicaje por Caja: 0.0634 m³/CBM "
        "Peso neto por caja: 7.5 Kg. Peso bruto por caja: 8.5 Kg. "
        "Leer Menos Certificado SGS"
    )
    assert "Color: Amarillo, Blanco" not in result[0].description
    assert "Descripción comercial" not in result[0].description
    assert "Información adicional" not in result[0].description
    assert "Valoraciones" not in result[0].description
    assert category_scraper.detail_requests == [
        "https://example.com/producto/muneco-antiestres/"
    ]
    assert scraper.get_detail_metrics()["detail_requests"] == 1


def test_color_only_card_detail_does_not_fall_back_to_description_tab():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/producto-solo-color/">
                <img src="https://example.com/producto-real.jpg">
                <h2 class="brxe-f31760">Producto con color solamente</h2>
            </a>
            <p class="brxe-a26f34">FB-4016</p>
            <div class="text-content">Colores Blanco</div>
            <div class="variaciones-producto"><p>10</p></div>
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Producto con color solamente</h1>
        <p class="brxe-heading">FB-4016</p>
        <div class="text-content">Colores: Rojo, Azul.</div>
        <div id="tab-description" class="woocommerce-Tabs-panel--description">
            Material: ABS. Peso neto por caja: 5.5 Kg.
        </div>
        <img class="woocommerce-product-gallery"
             src="https://example.com/producto-real.jpg">
        <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
        <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        Stock Disponible 10
    </html>
    """

    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert category_scraper.detail_requests == [
        "https://example.com/producto/producto-solo-color/"
    ]
    assert result[0].description == ""


def test_empty_identified_card_detail_stays_empty_when_page_has_detail():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/producto-detalle-vacio/">
                <img src="https://example.com/Logo-Facundo-2026.webp">
                <h2 class="brxe-f31760">Producto con Detalle vacío</h2>
            </a>
            <p class="brxe-a26f34">FB-1242</p>
            <div class="text-content"></div>
            <div class="brxe-text-basic">Material: ABS. Dimensiones: 99 x 99 cm.</div>
            <div class="variaciones-producto"><p>10</p></div>
            <div class="content-precio">
                <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
            </div>
            <div class="content-precio">
                <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
            </div>
            <div class="content-precio">
                <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
            </div>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Producto con Detalle vacío</h1>
        <p class="brxe-heading">FB-1242</p>
        <div class="woocommerce-product-details__short-description">
            Material: PLÁSTICO. Dimensiones: 99 x 99 cm.
        </div>
        <img class="woocommerce-product-gallery"
             src="https://example.com/producto-real.webp">
        <div class="content-precio">
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </div>
        Stock Disponible 10
    </html>
    """

    result = scraper.scrape_category(
        Category(
            name="Promocionales",
            url="https://example.com/promocionales/",
        )
    )

    assert len(result) == 1
    assert category_scraper.detail_requests == [
        "https://example.com/producto/producto-detalle-vacio/"
    ]
    assert result[0].description == ""


def test_bare_colores_text_triggers_technical_detail_repair():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/antiestres-cerebro-largo/">
                <img src="https://example.com/fb-4008.webp">
                <h2 class="brxe-f31760">Antiestrés Cerebro Largo</h2>
            </a>
            <p class="brxe-a26f34">FB-4008</p>
            <div class="text-content">Colores Blanco</div>
            <div class="variaciones-producto"><p>7819</p></div>
            <div class="content-precio">
                <h3>Precio Muestra</h3><h4>S/ 4.00</h4>
            </div>
            <div class="content-precio">
                <h3>Precio Ciento</h3><h4>S/ 300.00</h4>
            </div>
            <div class="content-precio">
                <h3>Precio Millar</h3><h4>S/ 2800.00</h4>
            </div>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Antiestrés Cerebro Largo</h1>
        <p class="brxe-heading">FB-4008</p>
        <div class="woocommerce-product-details__short-description">
            Material: Poliuretano. Dimensiones: 85*95*50mm.
            Peso Unitario: 25.4 G. Uso Recomendado: Antiestrés, Promocional.
        </div>
        <div id="tab-description" class="woocommerce-Tabs-panel--description">
            Descripción comercial que no debe ser usada como Detalle.
        </div>
        <img class="woocommerce-product-gallery"
             src="https://example.com/fb-4008.webp">
        <div class="content-precio">
            <h3>Precio Muestra</h3><h4>S/ 4.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3><h4>S/ 300.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3><h4>S/ 2800.00</h4>
        </div>
        Stock Disponible 7819
    </html>
    """

    result = scraper.scrape_category(
        Category(name="Artículos Antiestrés", url="https://example.com/antiestres/")
    )

    assert len(result) == 1
    assert result[0].code == "FB-4008"
    assert result[0].description == (
        "Material: Poliuretano. Dimensiones: 85*95*50mm. "
        "Peso Unitario: 25.4 G. Uso Recomendado: Antiestrés, Promocional."
    )
    assert "Colores Blanco" not in result[0].description
    assert "Descripción comercial" not in result[0].description
    assert category_scraper.detail_requests == [
        "https://example.com/producto/antiestres-cerebro-largo/"
    ]


def test_fb4008_truncated_card_uses_full_woocommerce_short_description():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/antiestres-cerebro-largo/">
                <h2 class="brxe-f31760">Antiestrés Cerebro Largo</h2>
            </a>
            <p class="brxe-a26f34">FB-4008</p>
            <div class="text-content">
                Color: Blanco. Material: Poliuretano. Dimensiones: 75*63*48mm.
                Peso Unitario: 23.5 G. Uso Recomendado: Antiestrés,
            </div>
            <div class="variaciones-producto"><p>8384</p></div>
            <div class="content-precio">
                <h3>Precio Muestra</h3><h4>S/ 4.00</h4>
            </div>
            <div class="content-precio">
                <h3>Precio Ciento</h3><h4>S/ 300.00</h4>
            </div>
            <div class="content-precio">
                <h3>Precio Millar</h3><h4>S/ 2800.00</h4>
            </div>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Antiestrés Cerebro Largo</h1>
        <p class="brxe-heading">FB-4008</p>
        <div class="woocommerce-product-details__short-description">
            <ul>
                <li>Color: Blanco.</li>
                <li>Material: Poliuretano.</li>
                <li>Dimensiones: 75*63*48mm.</li>
                <li>Peso Unitario: 23.5 G.</li>
                <li>Uso Recomendado: Antiestrés, Promocional.</li>
                <li>Empaque Individual: Bolsa de polietileno.</li>
                <li>Cantidad Por Caja: 250 Pza.</li>
                <li>Dimensiones Caja: 50*42*42cm.</li>
                <li>Cubicaje por Caja: 0.0882 m³/CBM.</li>
                <li>Peso neto por caja: 5.5 Kg.</li>
                <li>Peso bruto por caja: 6.25 Kg.</li>
            </ul>
        </div>
        <div id="tab-description" class="woocommerce-Tabs-panel--description">
            Descripción comercial: no debe reemplazar el Detalle técnico.
        </div>
        <div id="tab-additional_information">
            Información adicional: tampoco es la fuente del Detalle.
        </div>
        <div id="tab-reviews">Valoraciones que deben ignorarse.</div>
        <img class="woocommerce-product-gallery"
             src="https://example.com/fb-4008.webp">
        <div class="content-precio">
            <h3>Precio Muestra</h3><h4>S/ 4.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3><h4>S/ 300.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3><h4>S/ 2800.00</h4>
        </div>
        Stock Disponible 8384
    </html>
    """

    result = scraper.scrape_category(
        Category(
            name="Artículos Antiestrés",
            url="https://example.com/articulos-antiestres/",
        )
    )

    assert len(result) == 1
    assert result[0].code == "FB-4008"
    assert result[0].description == (
        "Material: Poliuretano. Dimensiones: 75*63*48mm. "
        "Peso Unitario: 23.5 G. Uso Recomendado: Antiestrés, Promocional. "
        "Empaque Individual: Bolsa de polietileno. Cantidad Por Caja: 250 Pza. "
        "Dimensiones Caja: 50*42*42cm. Cubicaje por Caja: 0.0882 m³/CBM. "
        "Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg."
    )
    assert "Color: Blanco" not in result[0].description
    assert "Descripción comercial" not in result[0].description
    assert "Información adicional" not in result[0].description
    assert category_scraper.detail_requests == [
        "https://example.com/producto/antiestres-cerebro-largo/"
    ]
    assert scraper.get_detail_metrics()["detail_requests"] == 1


def test_incomplete_card_is_not_replaced_by_generic_color_text_from_detail_page():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/producto-sin-detalle-especifico/">
                <img src="https://example.com/producto-real.jpg">
                <h2 class="brxe-f31760">Producto con detalle truncado</h2>
            </a>
            <p class="brxe-a26f34">FB-4013</p>
            <div class="text-content">
                Material: ABS. Peso neto por caja: 5.5 Kg. Peso bruto por...
            </div>
            <div class="variaciones-producto"><p>10</p></div>
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </article>
    </html>
    """
    category_scraper.detail_html_override = """
    <html>
        <h1>Producto con detalle truncado</h1>
        <p class="brxe-heading">FB-4013</p>
        <div class="text-content">Colores disponibles: Blanco, Azul.</div>
        <img class="woocommerce-product-gallery"
             src="https://example.com/producto-real.jpg">
        <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
        <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        Stock Disponible 10
    </html>
    """

    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert len(category_scraper.detail_requests) == 1
    assert result[0].description == (
        "Material: ABS. Peso neto por caja: 5.5 Kg. Peso bruto por..."
    )
    assert "Colores disponibles" not in result[0].description


def test_detail_failure_keeps_category_card_detail_as_the_source():
    category_scraper = SharedProductCategoryScraper()
    category_scraper.detail_html_override = ""
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    category_scraper.html_override = """
    <html>
        <article>
            <a href="/producto/producto-sin-detalle/">
                <h2 class="brxe-f31760">Producto sin detalle</h2>
            </a>
            <p class="brxe-a26f34">FB-1241</p>
            <div class="text-content">
                Material: ABS. Peso neto por caja: 5.5 Kg. Peso bruto por...
            </div>
            <div class="variaciones-producto"><p>10</p></div>
        </article>
    </html>
    """

    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert result[0].description == (
        "Material: ABS. Peso neto por caja: 5.5 Kg. Peso bruto por..."
    )
