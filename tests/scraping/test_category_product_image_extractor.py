from bs4 import BeautifulSoup

from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)


def test_extract_product_main_image():
    html = """
    <article>
        <a href="/producto/fb-1812">
            <img
                src="data:image/svg+xml"
                data-src="https://site.com/Proximo.webp"
            >
            <img
                src="data:image/svg+xml"
                data-src="https://site.com/FB-1812-300x300.webp"
            >
            <img
                src="data:image/svg+xml"
                data-src="https://site.com/Logo-Facundo.webp"
            >
            <img
                src="https://site.com/box-product-03.webp"
            >
        </a>
    </article>
    """

    soup = BeautifulSoup(html, "html.parser")
    product = CategoryProductExtractor().extract(soup)

    assert product.image_url == "https://site.com/FB-1812.webp"
