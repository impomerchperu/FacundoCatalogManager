from pathlib import Path

import scrapers.images.product_image_storage as storage_module
from models.product import Product
from services.scraping import image_review_service as module
from services.scraping.image_review_service import ImageReviewService
from tests.scraping.image_test_utils import image_bytes


class FakeRepository:
    def __init__(self, product):
        self.product = product

    def get_by_code(self, code):
        if self.product is None:
            return None
        return self.product if self.product.code == code else None

    def update(self, product):
        self.product = product
        return product


def _patch_paths(monkeypatch, tmp_path):
    queue_path = tmp_path / "queue.json"
    staging_dir = tmp_path / "image_review_staging"
    products_dir = tmp_path / "data" / "images" / "products"
    gallery_dir = tmp_path / "data" / "images" / "gallery"
    monkeypatch.setattr(module, "QUEUE_PATH", queue_path)
    monkeypatch.setattr(module, "STAGING_DIR", staging_dir)
    monkeypatch.setattr(module, "IMAGE_PRODUCTS_DIR", products_dir)
    monkeypatch.setattr(module, "IMAGE_GALLERY_DIR", gallery_dir)
    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: value if Path(value).is_absolute() else tmp_path / value,
    )
    monkeypatch.setattr(
        storage_module,
        "to_data_relative_path",
        lambda value: str(Path(value).resolve().relative_to(tmp_path)).replace(
            "\\",
            "/",
        ),
    )
    monkeypatch.setattr(
        module,
        "to_data_relative_path",
        lambda value: str(Path(value).resolve().relative_to(tmp_path)).replace(
            "\\",
            "/",
        ),
    )
    return staging_dir, products_dir


def test_image_review_keeps_manual_only_record_pending(
    monkeypatch,
    tmp_path,
):
    staging_dir, _products_dir = _patch_paths(monkeypatch, tmp_path)
    current = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_path="data/images/products/FB-4010.webp",
        image_hash="old-hash",
        image_url="https://site.test/uploads/Logo-Facundo-2026.webp",
    )
    service = ImageReviewService(FakeRepository(current))

    service.register_candidate(
        code="FB-4010",
        product_name="Gota Antiestrés",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="",
        candidate_hash="",
        candidate_url="",
        candidate_options=[],
        allow_manual_only=True,
    )

    pending = service.pending()

    assert len(pending) == 1
    assert pending[0]["manual_only"] is True
    assert pending[0]["candidate_options"] == []
    assert not staging_dir.exists()


def test_image_review_allows_selecting_a_second_gallery_candidate(
    monkeypatch,
    tmp_path,
):
    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    current_path = products_dir / "FB-4010.webp"
    first_path = staging_dir / "first.webp"
    second_path = staging_dir / "second.webp"
    products_dir.mkdir(parents=True)
    staging_dir.mkdir(parents=True)
    current_path.write_bytes(image_bytes("WEBP", (1, 2, 3)))
    first_path.write_bytes(image_bytes("WEBP", (4, 5, 6)))
    second_path.write_bytes(image_bytes("WEBP", (7, 8, 9)))

    current = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_path="data/images/products/FB-4010.webp",
        image_hash="old-hash",
        image_url="https://site.test/old.webp",
    )
    service = ImageReviewService(FakeRepository(current))
    service.register_candidate(
        code="FB-4010",
        product_name="Gota Antiestrés",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path=str(
            first_path.relative_to(tmp_path).as_posix()
        ),
        candidate_hash="first-hash",
        candidate_url="https://site.test/first.webp",
        candidate_options=[
            {
                "path": str(first_path.relative_to(tmp_path)).replace("\\", "/"),
                "hash": "first-hash",
                "url": "https://site.test/first.webp",
                "score": 400,
                "exact_code": False,
                "generic": False,
                "gallery": True,
            },
            {
                "path": str(second_path.relative_to(tmp_path)).replace("\\", "/"),
                "hash": "second-hash",
                "url": "https://site.test/second.webp",
                "score": 390,
                "exact_code": False,
                "generic": False,
                "gallery": True,
            },
        ],
    )

    record_id = service.pending()[0]["id"]
    result = service.apply_selection(
        record_id,
        "candidate",
        manual_path="image_review_staging/second.webp",
    )

    assert result["selected"] is True
    pending = service.pending()[0]
    assert pending["selected_action"] == "candidate"
    assert pending["selected_path"] == "image_review_staging/second.webp"
    assert pending["selected_url"] == "https://site.test/second.webp"


def test_image_review_defers_gallery_dismissal_until_batch_finishes(
    monkeypatch,
    tmp_path,
):
    _staging_dir, _products_dir = _patch_paths(monkeypatch, tmp_path)
    gallery_dir = tmp_path / "data" / "images" / "gallery" / "FB-4010"
    monkeypatch.setattr(module, "IMAGE_GALLERY_DIR", tmp_path / "data" / "images" / "gallery")
    gallery_dir.mkdir(parents=True)
    first = gallery_dir / "FB-4010-01.webp"
    second = gallery_dir / "FB-4010-02.webp"
    first.write_bytes(image_bytes("WEBP", (10, 20, 30)))
    second.write_bytes(image_bytes("WEBP", (40, 50, 60)))

    current = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_path="data/images/products/FB-4010.webp",
        image_hash="old-hash",
        image_url="https://site.test/one.webp",
        gallery_images=[
            {
                "url": "https://site.test/one.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-01.webp",
                "image_hash": "first",
                "position": 1,
                "source": "woocommerce-gallery",
            },
            {
                "url": "https://site.test/two.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-02.webp",
                "image_hash": "second",
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )

    def cleanup_unreferenced():
        references = {
            Path(module.resolve_data_path(image.get("image_path", ""))).resolve()
            for image in current.gallery_images
            if image.get("image_path")
        }
        if current.image_path:
            references.add(
                Path(module.resolve_data_path(current.image_path)).resolve()
            )
        for path in (first, second):
            if path.resolve() not in references:
                path.unlink(missing_ok=True)
        return []

    service = ImageReviewService(
        FakeRepository(current),
        image_cleanup=cleanup_unreferenced,
    )
    batch = service.begin_batch()
    service.register_candidate(
        code="FB-4010",
        product_name="Gota Antiestrés",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="data/images/gallery/FB-4010/FB-4010-01.webp",
        candidate_hash="first",
        candidate_url="https://site.test/one.webp",
        candidate_options=[
            {
                "path": "data/images/gallery/FB-4010/FB-4010-01.webp",
                "hash": "first",
                "url": "https://site.test/one.webp",
                "gallery": True,
            },
            {
                "path": "data/images/gallery/FB-4010/FB-4010-02.webp",
                "hash": "second",
                "url": "https://site.test/two.webp",
                "gallery": True,
            },
        ],
        kind="gallery",
    )

    record_id = service.available()[0]["id"]
    result = service.apply_selection(record_id, "dismiss_gallery")

    assert result["selected"] is True
    assert service.available()[0]["status"] == "staged"
    assert current.gallery_images
    assert first.exists()
    assert second.exists()

    service.finalize_batch(batch)
    service.apply_approved(batch)

    assert current.gallery_images == []
    assert not first.exists()
    assert not second.exists()
    assert service.pending() == []


def test_image_review_excluded_gallery_candidate_is_removed_only_on_apply(
    monkeypatch,
    tmp_path,
):
    _staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    gallery_dir = tmp_path / "data" / "images" / "gallery" / "FB-4010"
    monkeypatch.setattr(
        module,
        "IMAGE_GALLERY_DIR",
        tmp_path / "data" / "images" / "gallery",
    )
    gallery_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)
    first = gallery_dir / "FB-4010-01.webp"
    second = gallery_dir / "FB-4010-02.webp"
    first.write_bytes(image_bytes("WEBP", (10, 20, 30)))
    second.write_bytes(image_bytes("WEBP", (40, 50, 60)))

    current = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_path="data/images/products/FB-4010.webp",
        image_hash="old-hash",
        image_url="https://site.test/old.webp",
        gallery_images=[
            {
                "url": "https://site.test/first.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-01.webp",
                "image_hash": "first",
                "position": 1,
                "source": "woocommerce-gallery",
            },
            {
                "url": "https://site.test/second.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-02.webp",
                "image_hash": "second",
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )

    def cleanup_unreferenced():
        references = {
            Path(module.resolve_data_path(image.get("image_path", ""))).resolve()
            for image in current.gallery_images
            if image.get("image_path")
        }
        if current.image_path:
            references.add(
                Path(module.resolve_data_path(current.image_path)).resolve()
            )
        for path in (first, second):
            if path.resolve() not in references:
                path.unlink(missing_ok=True)
        return []

    service = ImageReviewService(
        FakeRepository(current),
        image_cleanup=cleanup_unreferenced,
    )
    service.register_candidate(
        code="FB-4010",
        product_name="Gota Antiestrés",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="data/images/gallery/FB-4010/FB-4010-01.webp",
        candidate_hash="first",
        candidate_url="https://site.test/first.webp",
        candidate_options=[
            {
                "path": "data/images/gallery/FB-4010/FB-4010-01.webp",
                "hash": "first",
                "url": "https://site.test/first.webp",
                "gallery": True,
            },
            {
                "path": "data/images/gallery/FB-4010/FB-4010-02.webp",
                "hash": "second",
                "url": "https://site.test/second.webp",
                "gallery": True,
            },
        ],
        kind="gallery",
    )
    review_id = service.pending()[0]["id"]

    service.exclude_candidate(
        review_id,
        "data/images/gallery/FB-4010/FB-4010-02.webp",
    )

    assert len(current.gallery_images) == 2
    assert second.exists()

    result = service.finalize_selected([review_id])

    assert result[0]["changed"] is True
    assert [
        image["url"]
        for image in current.gallery_images
    ] == ["https://site.test/first.webp"]
    canonical = Path(
        module.resolve_data_path(current.gallery_images[0]["image_path"])
    )
    assert canonical.is_file()
    assert not first.exists()
    assert not second.exists()
    assert service.pending() == []
