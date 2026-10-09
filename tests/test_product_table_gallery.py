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
