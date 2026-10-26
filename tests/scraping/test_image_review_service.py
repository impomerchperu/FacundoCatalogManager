import hashlib
from pathlib import Path

import pytest

import scrapers.images.product_image_storage as storage_module
from database.db_manager import DBManager
from models.product import Product
from repositories.product_repository import ProductRepository
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


def test_image_review_batch_is_hidden_until_finalize(monkeypatch, tmp_path):
    staging_dir, _products_dir = _patch_paths(monkeypatch, tmp_path)
    candidate = staging_dir / "FB-100-new.jpg"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(image_bytes("JPEG", (1, 2, 3)))

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
    current_path.write_bytes(image_bytes("JPEG", (4, 5, 6)))
    candidate_path.write_bytes(image_bytes("WEBP", (7, 8, 9)))

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

    destination = products_dir / "FB-100" / "FB-100-01.webp"
    assert result["changed"] is False
    assert repository.product.image_path == "data/images/products/FB-100.jpg"
    assert repository.product.image_url == "https://example.test/old.jpg"
    assert candidate_path.exists()

    finalized = service.finalize_selected([review_id])

    assert finalized[0]["changed"] is True
    assert repository.product.image_path == "data/images/products/FB-100/FB-100-01.webp"
    assert repository.product.image_url == "https://example.test/new.webp"
    assert destination.read_bytes() == image_bytes("WEBP", (7, 8, 9))
    assert current_path.read_bytes() == image_bytes("JPEG", (4, 5, 6))
    assert not candidate_path.exists()
    assert service.pending() == []


def test_image_review_keep_restores_current_image_metadata(monkeypatch, tmp_path):
    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    candidate = staging_dir / "FB-100-new.jpg"
    candidate.parent.mkdir(parents=True)
    products_dir.mkdir(parents=True)
    candidate.write_bytes(image_bytes("JPEG", (10, 11, 12)))
    current_path = products_dir / "FB-100.jpg"
    current_bytes = image_bytes("JPEG", (4, 5, 6))
    current_path.write_bytes(current_bytes)

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

    assert finalized[0]["changed"] is True
    assert repository.product.image_path == (
        "data/images/products/FB-100/FB-100-01.jpg"
    )
    assert repository.product.image_hash == hashlib.sha256(current_bytes).hexdigest()
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
    current_path.write_bytes(image_bytes("JPEG", (4, 5, 6)))
    candidate_path.write_bytes(image_bytes("WEBP", (16, 17, 18)))

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
    assert persisted.image_path == "data/images/products/FB-100/FB-100-01.webp"
    assert persisted.image_hash
    reopened.db.close()


def test_manual_image_selection_clears_remote_source_and_http_validators(
    monkeypatch,
    tmp_path,
):
    _, products_dir = _patch_paths(monkeypatch, tmp_path)
    product_dir = products_dir / "FB-101"
    product_dir.mkdir(parents=True)
    current_path = product_dir / "FB-101-01.jpg"
    current_path.write_bytes(image_bytes("JPEG", (4, 5, 6)))
    manual_path = tmp_path / "manual.webp"
    manual_path.write_bytes(image_bytes("WEBP", (13, 14, 15)))

    current = Product(
        code="FB-101",
        name="Producto",
        image_url="https://example.test/FB-101.jpg",
        image_path="data/images/products/FB-101/FB-101-01.jpg",
        image_hash="old-hash",
        image_etag='"old-etag"',
        image_last_modified="Sun, 18 Oct 2026 00:00:00 GMT",
        image_checked_at="2026-10-18T00:00:00+00:00",
    )
    service = ImageReviewService(FakeRepository(current))
    service.register_candidate(
        code="FB-101",
        product_name="Producto",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="",
        candidate_hash="",
        candidate_url="",
        allow_manual_only=True,
    )

    review_id = service.pending()[0]["id"]
    service.apply_selection(review_id, "manual", manual_path)
    service.finalize_selected([review_id])

    assert current.image_path == "data/images/products/FB-101/FB-101-01.webp"
    assert (products_dir / "FB-101" / "FB-101-01.webp").is_file()
    assert current.image_url == ""
    assert current.image_hash
    assert current.image_etag == ""
    assert current.image_last_modified == ""
    assert current.image_checked_at == ""

def test_image_review_delete_current_clears_catalog_only_after_finalize(
    monkeypatch,
    tmp_path,
):
    _staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    products_dir.mkdir(parents=True)
    current_path = products_dir / "FB-100.jpg"
    current_path.write_bytes(image_bytes("JPEG", (4, 5, 6)))

    product = Product(
        code="FB-100",
        name="Producto",
        image_path="data/images/products/FB-100.jpg",
        image_hash="old-hash",
        image_url="https://example.test/old.jpg",
    )
    repository = FakeRepository(product)
    cleanup_observations = []

    def cleanup_after_persist():
        assert repository.product is not None
        assert repository.product.image_path == ""
        cleanup_observations.append(current_path.exists())
        current_path.unlink(missing_ok=True)
        return []

    service = ImageReviewService(
        repository,
        image_cleanup=cleanup_after_persist,
    )
    service.register_candidate(
        code="FB-100",
        product_name="Producto",
        current_path=product.image_path,
        current_hash=product.image_hash,
        current_url=product.image_url,
        candidate_path="",
        candidate_hash="",
        candidate_url="",
        allow_manual_only=True,
    )

    review_id = service.pending()[0]["id"]
    service.apply_selection(review_id, "delete")

    assert current_path.exists()
    assert repository.product.image_path == "data/images/products/FB-100.jpg"

    finalized = service.finalize_selected([review_id])

    assert finalized[0]["action"] == "delete"
    assert repository.product.image_path == ""
    assert repository.product.image_hash == ""
    assert repository.product.image_url == ""
    assert cleanup_observations == [True]
    assert not current_path.exists()
    assert service.pending() == []


def test_image_review_discards_transient_selections_without_changing_product(
    monkeypatch,
    tmp_path,
):
    staging_dir, _products_dir = _patch_paths(monkeypatch, tmp_path)
    staging_dir.mkdir(parents=True)
    candidate_path = staging_dir / "FB-100-new.webp"
    candidate_path.write_bytes(image_bytes("WEBP", (22, 23, 24)))

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
    candidate_path.write_bytes(image_bytes("WEBP", (19, 20, 21)))

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


def test_reviewed_observation_is_archived_and_new_source_can_be_reviewed(
    monkeypatch,
    tmp_path,
):
    import hashlib
    import json

    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    staging_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)

    current_path = products_dir / "FB-100.jpg"
    candidate_path = staging_dir / "FB-100-observed.webp"
    current_path.write_bytes(image_bytes("JPEG", (10, 11, 12)))
    candidate_bytes = image_bytes("WEBP", (13, 14, 15))
    candidate_path.write_bytes(candidate_bytes)

    current_hash = hashlib.sha256(current_path.read_bytes()).hexdigest()
    current = Product(
        code="FB-100",
        name="Product",
        image_path="data/images/products/FB-100.jpg",
        image_hash=current_hash,
        image_url="https://example.test/current.jpg",
    )
    service = ImageReviewService(FakeRepository(current))
    image_url = "https://example.test/uploads/candidate.webp"
    first_page = "https://example.test/product/first/"
    candidate_hash = hashlib.sha256(candidate_bytes).hexdigest()

    def register(page_url):
        return service.register_candidate(
            code="FB-100",
            product_name="Product",
            current_path=current.image_path,
            current_hash=current.image_hash,
            current_url=current.image_url,
            candidate_path="image_review_staging/FB-100-observed.webp",
            candidate_hash=candidate_hash,
            candidate_url=image_url,
            candidate_options=[
                {
                    "path": "image_review_staging/FB-100-observed.webp",
                    "hash": candidate_hash,
                    "url": image_url,
                    "source_page_url": page_url,
                    "extraction_source": "primary",
                    "generic": False,
                }
            ],
        )

    batch = service.begin_batch()
    assert register(first_page) is not None
    service.finalize_batch(batch)

    review_id = service.pending()[0]["id"]
    service.apply_selection(review_id, "keep")
    service.finalize_selected([review_id])

    ledger_path = service._observation_ledger_path()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    first_observation = next(
        item
        for item in ledger
        if item["source_page_url"] == first_page
        and item["code"] == "FB-100"
    )
    archived_file = ledger_path.parent / first_observation["stored_path"]
    assert first_observation["review_state"] == "reviewed"
    assert archived_file.is_file()

    # Same source, image and primary hash: do not reopen the same review.
    candidate_path.write_bytes(candidate_bytes)
    batch = service.begin_batch()
    assert register(first_page) is None
    service.finalize_batch(batch)
    assert service.pending() == []
    assert archived_file.is_file()

    # Identical bytes from a different product page require a separate review.
    second_page = "https://example.test/product/second/"
    candidate_path.write_bytes(candidate_bytes)
    batch = service.begin_batch()
    assert register(second_page) is not None
    service.finalize_batch(batch)

    pending = service.pending()
    assert len(pending) == 1
    assert pending[0]["candidate_options"][0]["source_page_url"] == second_page

    # A changed local primary hash also creates a fresh observation identity.
    current.image_hash = "changed-primary-hash"
    candidate_path.write_bytes(candidate_bytes)
    batch = service.begin_batch()
    assert register(first_page) is not None
    service.finalize_batch(batch)

    pending = service.pending()
    assert len(pending) == 1
    assert pending[0]["current_hash"] == "changed-primary-hash"
    assert pending[0]["candidate_options"][0]["source_page_url"] == first_page

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    observations = [
        item
        for item in ledger
        if item["code"] == "FB-100" and item["image_url"] == image_url
    ]
    assert {item["source_page_url"] for item in observations} == {
        first_page,
        second_page,
    }
    assert all(
        (ledger_path.parent / item["stored_path"]).is_file()
        for item in observations
    )


def test_generic_only_candidates_are_archived_but_not_queued_until_valid_image(
    monkeypatch,
    tmp_path,
):
    import hashlib
    import json

    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    staging_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)

    current_path = products_dir / "FB-100.jpg"
    current_bytes = image_bytes("JPEG", (20, 21, 22))
    current_path.write_bytes(current_bytes)
    current_hash = hashlib.sha256(current_bytes).hexdigest()
    current = Product(
        code="FB-100",
        name="Product",
        image_path="data/images/products/FB-100.jpg",
        image_hash=current_hash,
        image_url=(
            "https://example.test/uploads/Placeholder-img.webp"
        ),
    )
    service = ImageReviewService(FakeRepository(current))

    marker_path = staging_dir / "FB-100-marker.webp"
    marker_bytes = image_bytes("WEBP", (23, 24, 25))
    marker_path.write_bytes(marker_bytes)
    marker_hash = hashlib.sha256(marker_bytes).hexdigest()
    marker_url = (
        "https://example.test/uploads/Placeholder-img-600x600.webp"
    )

    batch = service.begin_batch()
    result = service.register_candidate(
        code="FB-100",
        product_name="Product",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="image_review_staging/FB-100-marker.webp",
        candidate_hash=marker_hash,
        candidate_url=marker_url,
        candidate_options=[
            {
                "path": "image_review_staging/FB-100-marker.webp",
                "hash": marker_hash,
                "url": marker_url,
                "source_page_url": "https://example.test/product/100/",
                "extraction_source": "primary",
                "generic": True,
            }
        ],
    )
    assert result is None
    service.finalize_batch(batch)
    assert service.pending() == []
    assert not marker_path.exists()

    ledger_path = service._observation_ledger_path()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    marker_observation = next(
        item for item in ledger if item["image_url"] == marker_url
    )
    marker_archive = ledger_path.parent / marker_observation["stored_path"]
    assert marker_observation["review_state"] == "observed_not_queued"
    assert marker_archive.is_file()

    valid_path = staging_dir / "FB-100-valid.webp"
    valid_bytes = image_bytes("WEBP", (26, 27, 28))
    valid_path.write_bytes(valid_bytes)
    valid_hash = hashlib.sha256(valid_bytes).hexdigest()
    valid_url = "https://example.test/uploads/FB-100-valid.webp"

    batch = service.begin_batch()
    result = service.register_candidate(
        code="FB-100",
        product_name="Product",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="image_review_staging/FB-100-valid.webp",
        candidate_hash=valid_hash,
        candidate_url=valid_url,
        candidate_options=[
            {
                "path": "image_review_staging/FB-100-valid.webp",
                "hash": valid_hash,
                "url": valid_url,
                "source_page_url": "https://example.test/product/100/",
                "extraction_source": "primary",
                "generic": False,
            }
        ],
    )
    assert result is not None
    service.finalize_batch(batch)

    pending = service.pending()
    assert len(pending) == 1
    assert pending[0]["candidate_hash"] == valid_hash
    assert marker_archive.is_file()

def test_manual_image_uses_detected_format_not_filename_suffix(
    monkeypatch,
    tmp_path,
):
    _staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    manual_path = tmp_path / "manual.webp"
    payload = image_bytes("PNG", (33, 44, 55))
    manual_path.write_bytes(payload)

    product = Product(
        code="FB-102",
        name="Producto",
        image_url="https://example.test/old.webp",
    )
    service = ImageReviewService(FakeRepository(product))
    service.register_candidate(
        code="FB-102",
        product_name="Producto",
        current_path="",
        current_hash="",
        current_url=product.image_url,
        candidate_path="",
        candidate_hash="",
        candidate_url="",
        allow_manual_only=True,
    )

    review_id = service.pending()[0]["id"]
    service.apply_selection(review_id, "manual", manual_path)
    record = service._read()[0]
    staged = module.ImageReviewService._resolve_staged_path(record["selected_path"])
    assert staged is not None
    assert staged.suffix == ".png"

    results = service.finalize_selected([review_id])

    canonical = products_dir / "FB-102" / "FB-102-01.png"
    assert results[0]["changed"] is True
    assert Path(product.image_path) == Path("data/images/products/FB-102/FB-102-01.png")
    assert canonical.is_file()
    assert canonical.read_bytes() == payload
    assert not staged.exists()


def test_manual_image_rejects_unidentifiable_content(
    monkeypatch,
    tmp_path,
):
    staging_dir, _products_dir = _patch_paths(monkeypatch, tmp_path)
    manual_path = tmp_path / "not-an-image.webp"
    manual_path.write_bytes(b"not an identifiable raster")

    product = Product(
        code="FB-103",
        name="Producto",
        image_url="https://example.test/old.webp",
        image_path="data/images/products/FB-103.webp",
        image_hash="old-hash",
    )
    service = ImageReviewService(FakeRepository(product))
    service.register_candidate(
        code="FB-103",
        product_name="Producto",
        current_path=product.image_path,
        current_hash=product.image_hash,
        current_url=product.image_url,
        candidate_path="",
        candidate_hash="",
        candidate_url="",
        allow_manual_only=True,
    )

    review_id = service.pending()[0]["id"]
    with pytest.raises(ValueError, match="imagen compatible e identificable"):
        service.apply_selection(review_id, "manual", manual_path)

    assert not staging_dir.exists() or not list(staging_dir.iterdir())
    assert service._read()[0].get("selected_action", "") != "manual"


def test_review_replacement_never_overwrites_active_canonical_image(
    monkeypatch,
    tmp_path,
):
    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    product_dir = products_dir / "FB-105"
    product_dir.mkdir(parents=True)
    staging_dir.mkdir(parents=True)
    active_path = product_dir / "FB-105-01.webp"
    active_bytes = image_bytes("WEBP", (60, 70, 80))
    candidate_bytes = image_bytes("WEBP", (90, 100, 110))
    active_path.write_bytes(active_bytes)
    candidate_path = staging_dir / "FB-105-next.webp"
    candidate_path.write_bytes(candidate_bytes)

    product = Product(
        code="FB-105",
        name="Producto",
        image_url="https://example.test/old.webp",
        image_path="data/images/products/FB-105/FB-105-01.webp",
        image_hash="old-recorded-hash",
    )
    repository = FakeRepository(product)
    cleanup_observations = []

    def cleanup_after_persist():
        assert repository.product.image_path != "data/images/products/FB-105/FB-105-01.webp"
        assert active_path.is_file()
        assert active_path.read_bytes() == active_bytes
        cleanup_observations.append(repository.product.image_path)
        active_path.unlink()
        return []

    service = ImageReviewService(
        repository,
        image_cleanup=cleanup_after_persist,
    )
    service.register_candidate(
        code="FB-105",
        product_name="Producto",
        current_path=product.image_path,
        current_hash=product.image_hash,
        current_url=product.image_url,
        candidate_path="image_review_staging/FB-105-next.webp",
        candidate_hash="new-hash",
        candidate_url="https://example.test/new.webp",
    )

    review_id = service.pending()[0]["id"]
    service.apply_selection(review_id, "replace")
    assert active_path.read_bytes() == active_bytes

    service.finalize_selected([review_id])

    assert cleanup_observations == [repository.product.image_path]
    assert not active_path.exists()
    assert repository.product.image_path != "data/images/products/FB-105/FB-105-01.webp"
    new_path = Path(module.resolve_data_path(repository.product.image_path))
    assert new_path.is_file()
    assert new_path.read_bytes() == candidate_bytes
def test_mixed_generic_and_valid_candidates_only_queues_valid_image(
    monkeypatch,
    tmp_path,
):
    import hashlib
    import json

    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    staging_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)

    current_path = products_dir / "FB-100.jpg"
    current_bytes = image_bytes("JPEG", (30, 31, 32))
    current_path.write_bytes(current_bytes)
    current_hash = hashlib.sha256(current_bytes).hexdigest()

    current = Product(
        code="FB-100",
        name="Product",
        image_path="data/images/products/FB-100.jpg",
        image_hash=current_hash,
        image_url="https://example.test/uploads/Placeholder-img.webp",
    )
    service = ImageReviewService(FakeRepository(current))

    marker_path = staging_dir / "FB-100-marker.webp"
    valid_path = staging_dir / "FB-100-valid.webp"
    marker_bytes = image_bytes("WEBP", (33, 34, 35))
    valid_bytes = image_bytes("WEBP", (36, 37, 38))
    marker_path.write_bytes(marker_bytes)
    valid_path.write_bytes(valid_bytes)

    marker_hash = hashlib.sha256(marker_bytes).hexdigest()
    valid_hash = hashlib.sha256(valid_bytes).hexdigest()
    marker_url = (
        "https://example.test/uploads/Placeholder-img-600x600.webp"
    )
    valid_url = "https://example.test/uploads/FB-100-valid.webp"
    source_page = "https://example.test/product/100/"

    batch = service.begin_batch()
    result = service.register_candidate(
        code="FB-100",
        product_name="Product",
        current_path=current.image_path,
        current_hash=current.image_hash,
        current_url=current.image_url,
        candidate_path="image_review_staging/FB-100-marker.webp",
        candidate_hash=marker_hash,
        candidate_url=marker_url,
        candidate_options=[
            {
                "path": "image_review_staging/FB-100-marker.webp",
                "hash": marker_hash,
                "url": marker_url,
                "source_page_url": source_page,
                "extraction_source": "primary",
                "generic": True,
            },
            {
                "path": "image_review_staging/FB-100-valid.webp",
                "hash": valid_hash,
                "url": valid_url,
                "source_page_url": source_page,
                "extraction_source": "primary",
                "generic": False,
            },
        ],
    )

    assert result is not None
    service.finalize_batch(batch)

    pending = service.pending()
    assert len(pending) == 1
    queued_urls = {
        option["url"] for option in pending[0]["candidate_options"]
    }
    assert valid_url in queued_urls
    assert marker_url not in queued_urls

    ledger_path = service._observation_ledger_path()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    marker = next(item for item in ledger if item["image_url"] == marker_url)
    valid = next(item for item in ledger if item["image_url"] == valid_url)

    assert marker["review_state"] == "observed_not_queued"
    assert valid["review_state"] == "queued"
    assert (ledger_path.parent / marker["stored_path"]).is_file()
    assert (ledger_path.parent / valid["stored_path"]).is_file()
    assert not marker_path.exists()
    assert valid_path.is_file()
def test_legacy_keep_without_provenance_does_not_hide_new_source_review(
    monkeypatch,
    tmp_path,
):
    import hashlib
    import json

    staging_dir, products_dir = _patch_paths(monkeypatch, tmp_path)
    staging_dir.mkdir(parents=True)
    products_dir.mkdir(parents=True)

    current_path = products_dir / "FB-100.jpg"
    current_bytes = image_bytes("JPEG", (40, 41, 42))
    current_path.write_bytes(current_bytes)
    current_hash = hashlib.sha256(current_bytes).hexdigest()

    candidate_path = staging_dir / "FB-100-observed.webp"
    candidate_bytes = image_bytes("WEBP", (43, 44, 45))
    candidate_path.write_bytes(candidate_bytes)
    candidate_hash = hashlib.sha256(candidate_bytes).hexdigest()

    candidate_url = "https://example.test/uploads/FB-100-observed.webp"
    source_page = "https://example.test/product/FB-100/"

    current = Product(
        code="FB-100",
        name="Product",
        image_path="data/images/products/FB-100.jpg",
        image_hash=current_hash,
        image_url="https://example.test/uploads/FB-100-current.jpg",
    )
    service = ImageReviewService(FakeRepository(current))

    # Reproduce an old resolved queue record without provenance metadata.
    service._write([{
        "id": "legacy-FB-100",
        "code": "FB-100",
        "status": "resolved",
        "resolution": "keep",
        "kind": "replacement",
        "current_hash": current_hash,
        "candidate_hash": candidate_hash,
        "candidate_url": candidate_url,
        "candidate_options": [{
            "path": "image_review_staging/FB-100-observed.webp",
            "hash": candidate_hash,
            "url": candidate_url,
        }],
    }])

    batch = service.begin_batch()
    result = service.register_candidate(
        code="FB-100",
        product_name="Product",
        current_path=current.image_path,
        current_hash=current_hash,
        current_url=current.image_url,
        candidate_path="image_review_staging/FB-100-observed.webp",
        candidate_hash=candidate_hash,
        candidate_url=candidate_url,
        candidate_options=[{
            "path": "image_review_staging/FB-100-observed.webp",
            "hash": candidate_hash,
            "url": candidate_url,
            "source_page_url": source_page,
            "extraction_source": "primary",
            "generic": False,
        }],
    )
    service.finalize_batch(batch)

    assert result is not None
    pending = service.pending()
    assert len(pending) == 1
    assert pending[0]["candidate_url"] == candidate_url
    assert candidate_path.is_file()

    ledger_path = service._observation_ledger_path()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    observation = next(
        item for item in ledger
        if item["code"] == "FB-100" and item["image_url"] == candidate_url
    )
    assert observation["review_state"] == "queued"
    assert observation["resolution"] == ""
    assert observation["source_page_url"] == source_page
    assert (ledger_path.parent / observation["stored_path"]).is_file()
