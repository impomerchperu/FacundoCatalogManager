from bs4 import BeautifulSoup

from scrapers.extractors.product_image_extractor import ProductImageExtractor


def test_product_image_extractor_prefers_first_valid_gallery_image():
    html = """
    <div class="woocommerce-product-gallery">
        <div class="woocommerce-product-gallery__image">
            <a href="https://site.test/uploads/SFPU-40-main.webp">
                <img
                    class="wp-post-image"
                    data-large_image="https://site.test/uploads/SFPU-40-main.webp"
                    src="https://site.test/uploads/SFPU-40-main-300x300.webp"
                    alt="Gota Antiestrés"
                >
            </a>
        </div>
        <div class="woocommerce-product-gallery__image">
            <a href="https://site.test/uploads/SFPU-40-copia-6.webp">
                <img
                    data-large_image="https://site.test/uploads/SFPU-40-copia-6.webp"
                    src="https://site.test/uploads/SFPU-40-copia-6-300x300.webp"
                    alt="Gota Antiestrés"
                >
            </a>
        </div>
    </div>
    """

    candidates = ProductImageExtractor.extract_candidates(
        BeautifulSoup(html, "html.parser"),
        code="FB-4010",
        name="Gota Antiestrés",
    )

    assert candidates
    assert candidates[0]["gallery"] is True
    assert candidates[0]["generic"] is False
    assert candidates[0]["url"] == "https://site.test/uploads/SFPU-40-main.webp"
    assert ProductImageExtractor.extract(
        BeautifulSoup(html, "html.parser"),
        code="FB-4010",
        name="Gota Antiestrés",
    ) == candidates[0]["url"]


def test_product_image_extractor_detects_generic_assets():
    values = (
        "https://site.test/uploads/Logo-Facundo-2026.webp",
        "https://site.test/uploads/woocommerce-placeholder.png",
        "https://site.test/uploads/ausente.webp",
        "https://site.test/uploads/sin-imagen.jpg",
    )

    for value in values:
        assert ProductImageExtractor.is_generic_asset(value) is True

    assert (
        ProductImageExtractor.is_generic_asset(
            "https://site.test/uploads/SFPU-40-copia-6.webp",
        )
        is False
    )


def test_product_image_extractor_keeps_valid_image_ahead_of_generic_image():
    html = """
    <article>
        <img src="https://site.test/uploads/Logo-Facundo-2026.webp">
        <img src="https://site.test/uploads/SFPU-40-copia-6.webp">
        <img src="https://site.test/uploads/box-product-03.webp">
    </article>
    """

    candidates = ProductImageExtractor.extract_candidates(
        BeautifulSoup(html, "html.parser"),
        code="FB-4010",
        name="Gota Antiestrés",
    )

    assert [item["generic"] for item in candidates[:2]] == [False, False]
    assert candidates[-1]["generic"] is True
    assert candidates[0]["url"] == (
        "https://site.test/uploads/SFPU-40-copia-6.webp"
    )
