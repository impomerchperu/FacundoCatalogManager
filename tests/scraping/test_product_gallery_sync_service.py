from pathlib import Path

from models.product import Product
from services.scraping.product_gallery_sync_service import (
    ProductGallerySyncService,
)


class FakeRepository:
    def __init__(self, products):
        self.products = {
            str(product.code).casefold(): product
            for product in products
        }
        self.bulk_calls = 0

    def get_by_codes(self, codes):
        self.bulk_calls += 1
        return {
            code.casefold(): self.products[code.casefold()]
            for code in codes
            if code.casefold() in self.products
        }


class FakeReviewService:
    def __init__(self, repository):
        self.repository = repository
        self.registered = []

    def register_candidate(self, **kwargs):
        self.registered.append(kwargs)
        return kwargs


class FakeDownloader:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.downloads = []

    def download_gallery(self, code, url, position, output_dir):
        del output_dir
        directory = self.tmp_path / "data" / "images" / "gallery" / code
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{code}-{position:02d}.webp"
        destination.write_bytes(url.encode("utf-8"))
        self.downloads.append(url)
        return str(destination.relative_to(self.tmp_path)).replace("\\", "/")


def _candidate(url, position):
    return {
        "url": url,
        "score": 400 - position,
        "exact_code": False,
        "generic": False,
        "gallery": True,
    }


def test_product_gallery_sync_downloads_new_gallery_images(
    monkeypatch,
    tmp_path,
):
    import services.scraping.product_gallery_sync_service as module

    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: (
            value
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )

    existing = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/one.webp",
        gallery_images=[
            {
                "url": "https://site.test/one.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-01.webp",
                "image_hash": "old",
                "position": 1,
                "source": "woocommerce-gallery",
            }
        ],
    )
    existing_path = tmp_path / existing.gallery_images[0]["image_path"]
    existing_path.parent.mkdir(parents=True)
    existing_path.write_bytes(b"old-image")

    repository = FakeRepository([existing])
    review = FakeReviewService(repository)
    downloader = FakeDownloader(tmp_path)
    product = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        url="https://site.test/producto/gota-antiestres/",
        image_url="https://site.test/one.webp",
    )
    product.image_candidates = [
        _candidate("https://site.test/one.webp", 1),
        _candidate("https://site.test/two.webp", 2),
    ]

    service = ProductGallerySyncService(
        browser=object(),
        product_extractor=object(),
        image_downloader=downloader,
        review_service=review,
        max_workers=2,
        max_candidates=6,
    )

    service.sync_products([product])

    assert repository.bulk_calls == 1
    assert downloader.downloads == ["https://site.test/two.webp"]
    assert [image["url"] for image in product.gallery_images] == [
        "https://site.test/one.webp",
        "https://site.test/two.webp",
    ]
    assert len(review.registered) == 1
    assert review.registered[0]["kind"] == "gallery"
    assert review.registered[0]["candidate_options"][0]["url"] == (
        "https://site.test/two.webp"
    )
