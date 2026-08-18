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
