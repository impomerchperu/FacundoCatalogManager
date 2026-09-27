from bs4 import BeautifulSoup

from scrapers.extractors.category_extractor import CategoryExtractor


def test_extract_categories():
    html = """
    <ul class="product-categories">
        <li>
            <a href="/categoria-producto/jarros-mug/">
                Jarros Mug
            </a>
        </li>
        <li>
            <a href="/categoria-producto/termos/">
                Termos
            </a>
        </li>
    </ul>
    """

    soup = BeautifulSoup(html, "lxml")
    categories = CategoryExtractor().extract(soup)

    assert len(categories) == 2
    assert categories[0].name == "Jarros Mug"
    assert categories[0].url == "/categoria-producto/jarros-mug/"
    assert categories[0].expected_count == 0


def test_extract_categories_reads_product_count_from_category_card():
    html = """
    <section class="category-card">
        <div>Producto(s) 61</div>
        <h3>Insumos de Sublimación</h3>
        <a href="/categoria-producto/insumos-de-sublimacion/">
            Ver Categoría
        </a>
    </section>
    """

    soup = BeautifulSoup(html, "lxml")
    category = CategoryExtractor().extract(soup)[0]

    assert category.name == "Insumos de Sublimación"
    assert category.expected_count == 61


def test_extract_categories_keeps_each_category_product_count_isolated():
    html = """
    <div class="category-card">
        <div>Producto(s) 61</div>
        <h3>Insumos de Sublimación</h3>
        <a href="/categoria-producto/insumos-de-sublimacion/">
            Ver Categoría
        </a>
    </div>
    <div class="category-card">
        <div>Producto(s) 31</div>
        <h3>Artículos de Escritorio</h3>
        <a href="/categoria-producto/articulos-de-escritorio/">
            Ver Categoría
        </a>
    </div>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "lxml"))

    assert [category.expected_count for category in categories] == [61, 31]


def test_extract_categories_deduplicates_same_category_url_variants():
    html = """
    <section>
        <h2>Nuestras Categorías</h2>
        <div>
            <div>
                <h3>Insumos de Sublimación</h3>
                <div>Producto(s) 61</div>
                <a href="https://stock.importacionesfacundo.com/categoria-producto/insumos-de-sublimacion/">
                    Ver Categoría
                </a>
            </div>
            <div>
                <h3>Insumos de Sublimación</h3>
                <div>Producto(s) 61</div>
                <a href="/categoria-producto/insumos-de-sublimacion/?view=mobile">
                    Ver Categoría
                </a>
            </div>
            <div>
                <h3>Insumos de Sublimación</h3>
                <div>Producto(s) 61</div>
                <a href="/categoria-producto/insumos-de-sublimacion">
                    Ver Categoría
                </a>
            </div>
            <div>
                <h3>Jarros Mug</h3>
                <div>Producto(s) 19</div>
                <a href="/categoria-producto/jarros-mug/">
                    Ver Categoría
                </a>
            </div>
        </div>
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "lxml"))

    assert len(categories) == 2
    assert [category.name for category in categories] == [
        "Insumos de Sublimación",
        "Jarros Mug",
    ]
    assert [category.expected_count for category in categories] == [61, 19]


def test_duplicate_category_links_merge_published_count():
    html = """
    <nav>
        <a href="/categoria-producto/papeles-fotograficos/">
            Papeles Fotográficos
        </a>
    </nav>
    <section>
        <div class="category-card">
            <span>Producto(s) 82</span>
            <h3>Papeles Fotográficos</h3>
            <a href="/categoria-producto/papeles-fotograficos/">
                Ver Categoría
            </a>
        </div>
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))

    assert len(categories) == 1
    assert categories[0].name == "Papeles Fotográficos"
    assert categories[0].expected_count == 82


def test_duplicate_category_links_keep_nonzero_count():
    html = """
    <section>
        <div>
            <span>Producto(s) 50</span>
            <h3>Artículos Antiestrés</h3>
            <a href="/categoria-producto/antiestres/">Ver Categoría</a>
        </div>
        <nav>
            <a href="/categoria-producto/antiestres/">Artículos Antiestrés</a>
        </nav>
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))

    assert len(categories) == 1
    assert categories[0].expected_count == 50


def test_only_public_catalog_category_cards_are_extracted():
    html = """
    <nav class="menu">
        <a href="/categoria-producto/cocina/">cocina</a>
        <a href="/categoria-producto/mesa-y-hogar/">mesa y hogar</a>
    </nav>
    <section class="catalog-categories">
        <h2>Nuestras Categorías</h2>
        <div class="category-card">
            <span>Producto(s) 18</span>
            <h3>Cocina, Mesa y Hogar</h3>
            <a href="/categoria-producto/cocina-mesa-y-hogar/">
                Ver Categoría
            </a>
        </div>
        <div class="category-card">
            <span>Producto(s) 82</span>
            <h3>Papeles Fotográficos</h3>
            <a href="/categoria-producto/papeles-fotograficos/">
                Ver Categoría
            </a>
        </div>
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))
    by_name = {category.name: category for category in categories}

    assert set(by_name) == {"Cocina, Mesa y Hogar", "Papeles Fotográficos"}
    assert by_name["Cocina, Mesa y Hogar"].expected_count == 18
    assert by_name["Papeles Fotográficos"].expected_count == 82
