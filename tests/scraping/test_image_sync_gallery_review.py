from models.product import Product
from scrapers.sync.image_sync import ImageSync


class FakeRepository:
    def __init__(self, product):
        self.product = product

    def get_by_codes(self, codes):
        return {self.product.code: self.product} if self.product else {}


class FakeImageRepository:
    def __init__(self, existing):
        self.existing = existing

    def find(self, code):
        del code
        return dict(self.existing)


class FakeDownloader:
    pass


class FakeReviewService:
    def __init__(self, repository):
        self.repository = repository
        self.registered = []
        self.discarded = []

    def stage_candidates(self, downloader, code, candidates, *, max_candidates=None):
        del downloader, code
        selected = list(candidates)
        if max_candidates is not None:
            selected = selected[:max_candidates]
        return [
            {
                **candidate,
                "path": f"image_review_staging/{index}.webp",
                "hash": f"hash-{index}",
            }
            for index, candidate in enumerate(selected, start=1)
        ]

    def register_candidate(self, **kwargs):
        self.registered.append(kwargs)
        return kwargs

    def discard_staged(self, path):
        self.discarded.append(path)


def test_image_sync_stages_gallery_alternatives_when_current_image_is_generic():
    current = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/uploads/Logo-Facundo-2026.webp",
        image_path="data/images/products/FB-4010.webp",
        image_hash="old-hash",
    )
    review = FakeReviewService(FakeRepository(current))
    sync = ImageSync(
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
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/uploads/SFPU-40-main.webp",
    )
    product.image_candidates = [
        {
            "url": "https://site.test/uploads/SFPU-40-main.webp",
            "score": 400,
            "exact_code": False,
            "generic": False,
            "gallery": True,
        },
        {
            "url": "https://site.test/uploads/SFPU-40-copia-6.webp",
            "score": 390,
            "exact_code": False,
            "generic": False,
            "gallery": True,
        },
    ]

    sync.process([product])

    assert len(review.registered) == 1
    assert len(review.registered[0]["candidate_options"]) == 2
    assert review.registered[0]["current_url"].endswith(
        "Logo-Facundo-2026.webp"
    )
