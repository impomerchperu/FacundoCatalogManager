from pathlib import Path

from models.product import Product
from services.scraping import image_review_service as module
from services.scraping.image_review_service import ImageReviewService


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
    staging_dir = tmp_path / "staging"
    products_dir = tmp_path / "products"
    monkeypatch.setattr(module, "QUEUE_PATH", queue_path)
    monkeypatch.setattr(module, "STAGING_DIR", staging_dir)
    monkeypatch.setattr(module, "IMAGE_PRODUCTS_DIR", products_dir)
    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: (
            value
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )
    return staging_dir, products_dir


def test_image_review_batch_is_hidden_until_finalize(monkeypatch, tmp_path):
    staging_dir, _products_dir = _patch_paths(monkeypatch, tmp_path)
    candidate = staging_dir / "FB-100-new.jpg"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"candidate")

    repository = FakeRepository(
        Product(
            code="FB-100",
            name="Producto",
            image_path="data/images/products/FB-100.jpg",
            image_hash="old-hash",
            image_url="https://example.test/old.jpg",
        )
    )
    service = ImageReviewService(repository)
    batch = service.begin_batch()
    service.register_candidate(
        code="FB-100",
        product_name="Producto",
        current_path="data/images/products/FB-100.jpg",
        current_hash="old-hash",
        current_url="https://example.test/old.jpg",
        candidate_path="image_review_staging/FB-100-new.jpg",
        candidate_hash="new-hash",
        candidate_url="https://example.test/new.jpg",
    )

    assert service.pending() == []
    service.finalize_batch(batch)
    assert len(service.pending()) == 1


def test_image_review_replace_updates_db_and_keeps_old_image_outside_staging(
    monkeypatch,
    tmp_path,
):
    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    current_path = products_dir / "FB-100.jpg"
    candidate_path = staging_dir / "FB-100-new.webp"
    products_dir.mkdir(parents=True)
    staging_dir.mkdir(parents=True)
    current_path.write_bytes(b"old-image")
    candidate_path.write_bytes(b"new-image")

    current = Product(
        code="FB-100",
        name="Producto",
        image_path="data/images/products/FB-100.jpg",
        image_hash="old-hash",
        image_url="https://example.test/old.jpg",
    )
    repository = FakeRepository(current)
    service = ImageReviewService(repository)
    service.register_candidate(
        code="FB-100",
        product_name="Producto",
        current_path="data/images/products/FB-100.jpg",
        current_hash="old-hash",
        current_url="https://example.test/old.jpg",
        candidate_path="image_review_staging/FB-100-new.webp",
        candidate_hash="new-hash",
        candidate_url="https://example.test/new.webp",
    )

    result = service.apply_selection(
        service.pending()[0]["id"],
        "replace",
    )

    destination = products_dir / "FB-100.webp"
    assert result["changed"] is True
    assert repository.product.image_path == "products/FB-100.webp"
    assert repository.product.image_url == "https://example.test/new.webp"
    assert destination.read_bytes() == b"new-image"
    assert current_path.read_bytes() == b"old-image"
    assert not candidate_path.exists()
    assert service.pending() == []


def test_image_review_keep_restores_current_image_metadata(monkeypatch, tmp_path):
    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    candidate = staging_dir / "FB-100-new.jpg"
    candidate.parent.mkdir(parents=True)
    products_dir.mkdir(parents=True)
    candidate.write_bytes(b"candidate")

    product = Product(
        code="FB-100",
        name="Producto",
        image_path="data/images/products/FB-100.jpg",
        image_hash="old-hash",
        image_url="https://example.test/new.jpg",
    )
    repository = FakeRepository(product)
    service = ImageReviewService(repository)
    service.register_candidate(
        code="FB-100",
        product_name="Producto",
        current_path="data/images/products/FB-100.jpg",
        current_hash="old-hash",
        current_url="https://example.test/old.jpg",
        candidate_path="image_review_staging/FB-100-new.jpg",
        candidate_hash="new-hash",
        candidate_url="https://example.test/new.jpg",
    )

    result = service.apply_selection(
        service.pending()[0]["id"],
        "keep",
    )

    assert result["changed"] is False
    assert repository.product.image_path == "data/images/products/FB-100.jpg"
    assert repository.product.image_hash == "old-hash"
    assert repository.product.image_url == "https://example.test/old.jpg"
    assert not candidate.exists()
    assert service.pending() == []
