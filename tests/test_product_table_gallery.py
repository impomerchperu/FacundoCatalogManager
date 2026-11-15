from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from gui.product_table import (
    ProductImageDelegate,
    ProductTable,
    _ScaledImageTask,
)
from models.product import Product


def _qapp():
    return QApplication.instance() or QApplication([])


class _Controller:
    def get_products(self):
        return []


def test_product_table_gallery_falls_back_to_primary_image():
    product = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/one.png",
        image_path="data/images/products/FB-4010.png",
        image_hash="hash-one",
    )

    gallery = ProductTable._product_gallery(product)

    assert gallery == [
        {
            "url": "https://site.test/one.png",
            "image_path": "data/images/products/FB-4010.png",
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
                "url": "https://site.test/one.png",
                "image_path": "data/images/gallery/FB-4010/01.png",
                "position": 1,
            },
            {
                "url": "https://site.test/two.png",
                "image_path": "data/images/gallery/FB-4010/02.png",
                "position": 2,
            },
        ],
    )

    gallery = ProductTable._product_gallery(product)

    assert [image["url"] for image in gallery] == [
        "https://site.test/one.png",
        "https://site.test/two.png",
    ]


def test_scaled_gallery_images_are_reused_for_the_same_size(tmp_path: Path):
    _qapp()
    image_path = str(tmp_path / "cached-product-image.png")
    first_key = (image_path, 60, 50)
    resized_key = (image_path, 80, 50)
    image = QPixmap(1200, 900)
    small = image.scaled(60, 50)
    resized = image.scaled(80, 50)
    ProductImageDelegate._scaled_pixmap_cache[first_key] = small
    ProductImageDelegate._scaled_pixmap_cache[resized_key] = resized

    delegate = ProductImageDelegate()
    first = delegate._load_scaled_pixmap(image_path, QSize(60, 50))
    second = delegate._load_scaled_pixmap(image_path, QSize(60, 50))
    larger = delegate._load_scaled_pixmap(image_path, QSize(80, 50))

    assert not first.isNull()
    assert first.cacheKey() == second.cacheKey()
    assert larger.cacheKey() != first.cacheKey()
    ProductImageDelegate._scaled_pixmap_cache.pop(first_key, None)
    ProductImageDelegate._scaled_pixmap_cache.pop(resized_key, None)


def test_scaled_image_task_decodes_within_requested_size(tmp_path: Path):
    _qapp()
    image_path = tmp_path / "large-product-image.png"
    image = QPixmap(1200, 900)
    assert image.save(str(image_path))
    results = []
    task = _ScaledImageTask(str(image_path), QSize(60, 50))
    task.signals.ready.connect(lambda *args: results.append(args))

    task.run()

    assert len(results) == 1
    decoded = results[0][-1]
    assert not decoded.isNull()
    assert decoded.width() <= 60
    assert decoded.height() <= 50


def test_product_table_deduplicates_primary_referenced_by_legacy_gallery():
    product = Product(
        code="FB-1507",
        name="Producto con imagen duplicada",
        image_url="https://site.test/FB-1507.png",
        image_path="data/images/products/FB-1507/FB-1507-01.png",
        image_hash="same-content",
        gallery_images=[
            {
                "url": "https://site.test/FB-1507.png",
                "image_path": "data/images/gallery/FB-1507/FB-1507-01.png",
                "image_hash": "same-content",
                "position": 1,
            },
            {
                "url": "https://site.test/FB-1507-side.png",
                "image_path": "data/images/gallery/FB-1507/FB-1507-02.png",
                "image_hash": "side-content",
                "position": 2,
            },
        ],
    )

    gallery = ProductTable._product_gallery(product)

    assert len(gallery) == 2
    assert gallery[0]["image_path"] == (
        "data/images/products/FB-1507/FB-1507-01.png"
    )
    assert gallery[0]["position"] == 1
    assert gallery[1]["url"] == "https://site.test/FB-1507-side.png"
    assert gallery[1]["position"] == 2


def test_gallery_overrides_deduplicate_by_hash_without_hiding_distinct_images(
    tmp_path: Path,
):
    _qapp()
    primary_path = tmp_path / "primary.png"
    duplicate_path = tmp_path / "duplicate.png"
    alternative_path = tmp_path / "alternative.png"
    for path in (primary_path, duplicate_path, alternative_path):
        image = QPixmap(32, 32)
        assert image.save(str(path))

    product = Product(
        code="FB-1507",
        name="Producto con galería",
        image_url="https://site.test/FB-1507.png",
        image_path=str(primary_path),
        image_hash="same-content",
    )
    table = ProductTable(_Controller())
    table.load_products([product])
    table.set_gallery_overrides(
        {
            "FB-1507": [
                {
                    "url": "https://site.test/FB-1507-duplicate.png",
                    "path": str(duplicate_path),
                    "hash": "same-content",
                },
                {
                    "url": "https://site.test/FB-1507-side.png",
                    "path": str(alternative_path),
                    "hash": "different-content",
                },
            ]
        }
    )

    image_item = table.item(0, ProductTable.IMAGE_COLUMN)
    gallery = image_item.data(ProductImageDelegate.GALLERY_ROLE)

    assert len(gallery) == 2
    assert gallery[0]["image_path"] == str(primary_path)
    assert gallery[1]["image_path"] == str(alternative_path)
    table.close()


def test_product_table_prefers_grouped_path_when_primary_is_legacy_flat_file():
    product = Product(
        code="FB-1507",
        name="Producto con rutas duplicadas",
        image_url="https://site.test/FB-1507.webp",
        image_path="data/images/products/FB-1507.webp",
        image_hash="same-content",
        gallery_images=[
            {
                "url": "https://site.test/FB-1507.webp",
                "image_path": "data/images/products/FB-1507/FB-1507-01.webp",
                "image_hash": "same-content",
                "position": 1,
            },
            {
                "url": "https://site.test/FB-1507-side.webp",
                "image_path": "data/images/products/FB-1507/FB-1507-02.webp",
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
    assert gallery[1]["image_path"] == (
        "data/images/products/FB-1507/FB-1507-02.webp"
    )
