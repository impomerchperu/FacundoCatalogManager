from gui.product_table import ProductImageDelegate, ProductTable
from models.product import Product


def test_product_table_gallery_falls_back_to_primary_image():
    product = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/one.webp",
        image_path="data/images/products/FB-4010.webp",
        image_hash="hash-one",
    )

    gallery = ProductTable._product_gallery(product)

    assert gallery == [
        {
            "url": "https://site.test/one.webp",
            "image_path": "data/images/products/FB-4010.webp",
            "image_hash": "hash-one",
            "position": 1,
            "source": "primary",
        }
    ]
    assert ProductImageDelegate.GALLERY_ROLE > ProductImageDelegate.IMAGE_ROLE


def test_product_table_gallery_preserves_multiple_images():
    product = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        gallery_images=[
            {
                "url": "https://site.test/one.webp",
                "image_path": "data/images/gallery/FB-4010/01.webp",
                "position": 1,
            },
            {
                "url": "https://site.test/two.webp",
                "image_path": "data/images/gallery/FB-4010/02.webp",
                "position": 2,
            },
        ],
    )

    gallery = ProductTable._product_gallery(product)

    assert [image["url"] for image in gallery] == [
        "https://site.test/one.webp",
        "https://site.test/two.webp",
    ]



def test_product_table_deduplicates_primary_referenced_by_legacy_gallery():
    product = Product(
        code="FB-1507",
        name="Producto con imagen duplicada",
        image_url="https://site.test/FB-1507.webp",
        image_path="data/images/products/FB-1507/FB-1507-01.webp",
        image_hash="same-content",
        gallery_images=[
            {
                "url": "https://site.test/FB-1507.webp",
                "image_path": "data/images/gallery/FB-1507/FB-1507-01.webp",
                "image_hash": "same-content",
                "position": 1,
            },
            {
                "url": "https://site.test/FB-1507-side.webp",
                "image_path": "data/images/gallery/FB-1507/FB-1507-02.webp",
                "image_hash": "side-content",
                "position": 2,
            },
        ],
    )

    gallery = ProductTable._product_gallery(product)

    assert len(gallery) == 2
    assert gallery[0]["image_path"] == (
        "data/images/products/FB-1507/FB-1507-01.webp"
    )
    assert gallery[0]["position"] == 1
    assert gallery[1]["url"] == "https://site.test/FB-1507-side.webp"
    assert gallery[1]["position"] == 2
