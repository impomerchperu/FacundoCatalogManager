from pathlib import Path

from database.db_manager import DBManager
from models.product import Product
from repositories.product_repository import ProductRepository
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
    staging_dir = tmp_path / "image_review_staging"
    products_dir = tmp_path / "data" / "images" / "products"
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
    monkeypatch.setattr(
        module,
        "to_data_relative_path",
        lambda value: str(Path(value).resolve().relative_to(tmp_path)).replace(
            "\\",
            "/",
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

    review_id = service.pending()[0]["id"]
    result = service.apply_selection(review_id, "replace")

    destination = products_dir / "FB-100.webp"
    assert result["changed"] is False
    assert repository.product.image_path == "data/images/products/FB-100.jpg"
    assert repository.product.image_url == "https://example.test/old.jpg"
    assert candidate_path.exists()

    finalized = service.finalize_selected([review_id])

    assert finalized[0]["changed"] is True
    assert repository.product.image_path == "data/images/products/FB-100.webp"
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

    review_id = service.pending()[0]["id"]
    result = service.apply_selection(review_id, "keep")

    assert result["changed"] is False
    assert repository.product.image_path == "data/images/products/FB-100.jpg"
    assert repository.product.image_hash == "old-hash"
    assert repository.product.image_url == "https://example.test/new.jpg"
    assert candidate.exists()

    finalized = service.finalize_selected([review_id])

    assert finalized[0]["changed"] is False
    assert repository.product.image_path == "data/images/products/FB-100.jpg"
    assert repository.product.image_hash == "old-hash"
    assert repository.product.image_url == "https://example.test/old.jpg"
    assert not candidate.exists()
    assert service.pending() == []


def test_image_review_apply_is_persisted_after_reopening_database(
    monkeypatch,
    tmp_path,
):
    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    db_path = tmp_path / "catalog.db"
    current_path = products_dir / "FB-100.jpg"
    candidate_path = staging_dir / "FB-100-new.webp"
    products_dir.mkdir(parents=True)
    staging_dir.mkdir(parents=True)
    current_path.write_bytes(b"old-image")
    candidate_path.write_bytes(b"new-image")

    db = DBManager(str(db_path))
    repository = ProductRepository(db)
    repository.create(
        Product(
            code="FB-100",
            name="Producto",
            image_path="data/images/products/FB-100.jpg",
            image_hash="old-hash",
            image_url="https://example.test/old.jpg",
        )
    )
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
    review_id = service.pending()[0]["id"]
    service.apply_selection(review_id, "replace")
    service.finalize_selected([review_id])
    db.close()

    reopened = ProductRepository(DBManager(str(db_path)))
    persisted = reopened.get_by_code("FB-100")

    assert persisted is not None
    assert persisted.image_url == "https://example.test/new.webp"
    assert persisted.image_path == "data/images/products/FB-100.webp"
    assert persisted.image_hash
    reopened.db.close()


def test_image_review_discards_transient_selections_without_changing_product(
    monkeypatch,
    tmp_path,
):
    staging_dir, _products_dir = _patch_paths(monkeypatch, tmp_path)
    staging_dir.mkdir(parents=True)
    candidate_path = staging_dir / "FB-100-new.webp"
    candidate_path.write_bytes(b"new-image")

    current = Product(
        code="FB-100",
        name="Producto",
        image_path="data/images/products/FB-100.jpg",
        image_hash="old-hash",
        image_url="https://example.test/old.jpg",
    )
    service = ImageReviewService(FakeRepository(current))
    service.register_candidate(
        code="FB-100",
        product_name="Producto",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="image_review_staging/FB-100-new.webp",
        candidate_hash="new-hash",
        candidate_url="https://example.test/new.webp",
    )
    review_id = service.pending()[0]["id"]
    service.apply_selection(review_id, "replace")

    service.discard_selections()

    assert current.image_url == "https://example.test/old.jpg"
    assert current.image_path == "data/images/products/FB-100.jpg"
    assert candidate_path.exists()
    record = service.pending()[0]
    assert not record.get("selected_action")


def test_new_scrape_batch_supersedes_previous_review_with_same_hash(
    monkeypatch,
    tmp_path,
):
    staging_dir, _products_dir = _patch_paths(monkeypatch, tmp_path)
    staging_dir.mkdir(parents=True)
    candidate_path = staging_dir / "FB-100-new.webp"
    candidate_path.write_bytes(b"candidate")

    current = Product(
        code="FB-100",
        name="Producto",
        image_path="data/images/products/FB-100.jpg",
        image_hash="old-hash",
        image_url="https://example.test/old.jpg",
    )
    service = ImageReviewService(FakeRepository(current))

    first_batch = service.begin_batch()
    service.register_candidate(
        code="FB-100",
        product_name="Producto",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="image_review_staging/FB-100-new.webp",
        candidate_hash="new-hash",
        candidate_url="https://example.test/new.webp",
    )
    service.finalize_batch(first_batch)
    first_id = service.pending()[0]["id"]
    service.apply_selection(first_id, "replace")

    second_batch = service.begin_batch()
    replacement = service.register_candidate(
        code="FB-100",
        product_name="Producto",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="image_review_staging/FB-100-new.webp",
        candidate_hash="new-hash",
        candidate_url="https://example.test/new.webp",
    )

    assert replacement is not None
    assert candidate_path.exists()
    records = service._read()
    superseded = next(record for record in records if record["id"] == first_id)
    assert superseded["status"] == "resolved"
    assert superseded["resolution"] == "superseded"

    service.finalize_batch(second_batch)
    pending = service.pending()

    assert len(pending) == 1
    assert pending[0]["id"] != first_id
