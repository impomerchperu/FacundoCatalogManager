from models.product import Product
from scrapers.sync.image_sync import ImageSync


class FakeRepository:
    def __init__(self, product):
        self.product = product

    def get_by_codes(self, codes):
        del codes
        if self.product is None:
            return {}
        return {self.product.code: self.product}


class FakeReviewService:
    def __init__(self, repository):
        self.repository = repository
        self.staged = {
            "image_path": "image_review_staging/FB-100-new.jpg",
            "image_hash": "new-hash",
        }
        self.registered = []

    def stage_candidate(self, downloader, code, url):
        self.staged["code"] = code
        self.staged["url"] = url
        return dict(self.staged)

    def discard_staged(self, path):
        self.staged["discarded"] = path

    def register_candidate(self, **kwargs):
        self.registered.append(kwargs)
        return kwargs


class FakeDownloader:
    pass


class FakeImageRepository:
    def __init__(self, result):
        self.result = result

    def find(self, code):
        del code
        return dict(self.result)


def test_image_sync_does_not_redownload_when_image_url_is_unchanged():
    current = Product(
        code="FB-100",
        name="Producto",
        image_url="https://example.test/FB-100.jpg",
        image_path="data/images/products/FB-100.jpg",
        image_hash="current-hash",
    )
    review = FakeReviewService(FakeRepository(current))
    image_sync = ImageSync(
        image_repository=FakeImageRepository(
            {
                "image_path": current.image_path,
                "image_hash": current.image_hash,
            }
        ),
        review_service=review,
        image_downloader=FakeDownloader(),
    )
    product = Product(
        code="FB-100",
        name="Producto",
        image_url=current.image_url,
    )

    result = image_sync.process([product])

    assert result[0].image_path == current.image_path
    assert result[0].image_hash == current.image_hash
    assert review.registered == []


def test_image_sync_stages_changed_image_without_replacing_current():
    current = Product(
        code="FB-100",
        name="Producto",
        image_url="https://example.test/FB-100-old.jpg",
        image_path="data/images/products/FB-100.jpg",
        image_hash="current-hash",
    )
    review = FakeReviewService(FakeRepository(current))
    image_sync = ImageSync(
        image_repository=FakeImageRepository(
            {
                "image_path": current.image_path,
                "image_hash": current.image_hash,
            }
        ),
        review_service=review,
        image_downloader=FakeDownloader(),
    )
    product = Product(
        code="FB-100",
        name="Producto",
        image_url="https://example.test/FB-100-new.jpg",
    )

    result = image_sync.process([product])

    assert result[0].image_path == current.image_path
    assert result[0].image_hash == current.image_hash
    assert len(review.registered) == 1
    assert review.registered[0]["candidate_url"] == product.image_url
    assert review.registered[0]["current_path"] == current.image_path
    assert review.registered[0]["current_hash"] == current.image_hash


def test_image_sync_discards_changed_image_when_content_hash_is_unchanged():
    current = Product(
        code="FB-100",
        name="Producto",
        image_url="https://example.test/FB-100-old.jpg",
        image_path="data/images/products/FB-100.jpg",
        image_hash="same-hash",
    )

    class SameHashReview(FakeReviewService):
        def stage_candidate(self, downloader, code, url):
            del downloader, code, url
            return {
                "image_path": "image_review_staging/FB-100-same.jpg",
                "image_hash": "same-hash",
            }

    review = SameHashReview(FakeRepository(current))
    image_sync = ImageSync(
        image_repository=FakeImageRepository(
            {
                "image_path": current.image_path,
                "image_hash": current.image_hash,
            }
        ),
        review_service=review,
        image_downloader=FakeDownloader(),
    )
    product = Product(
        code="FB-100",
        name="Producto",
        image_url="https://example.test/FB-100-new.jpg",
    )

    result = image_sync.process([product])

    assert result[0].image_path == current.image_path
    assert result[0].image_hash == current.image_hash
    assert review.staged["discarded"] == "image_review_staging/FB-100-same.jpg"
    assert review.registered == []
