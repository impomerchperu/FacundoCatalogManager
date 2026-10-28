import hashlib
from pathlib import Path

from models.product import Product
from models.scraping.scraped_product import ScrapedProduct
from services.scraping.product_gallery_sync_service import (
    ProductGallerySyncService,
)
from tests.scraping.image_test_utils import image_bytes


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
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{code}-{position:02d}.webp"
        seed = hashlib.sha256(url.encode("utf-8")).digest()
        destination.write_bytes(image_bytes("WEBP", (seed[0], seed[1], seed[2])))
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
            Path(value)
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )
    monkeypatch.setattr(module, "IMAGE_PRODUCTS_DIR", Path("data/images/products"))

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
    existing_path.write_bytes(image_bytes("WEBP", (1, 2, 3)))

    repository = FakeRepository([existing])
    review = FakeReviewService(repository)
    downloader = FakeDownloader(tmp_path)
    product = ScrapedProduct(
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
        refresh_existing=False,
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


def test_primary_image_is_reused_and_all_gallery_files_share_product_folder(
    monkeypatch,
    tmp_path,
):
    import services.scraping.product_gallery_sync_service as module

    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: (
            Path(value)
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )
    monkeypatch.setattr(module, "IMAGE_PRODUCTS_DIR", Path("data/images/products"))

    code = "FB-1507"
    product_dir = tmp_path / "data" / "images" / "products" / code
    product_dir.mkdir(parents=True)
    primary_path = product_dir / f"{code}-01.webp"
    primary_path.write_bytes(image_bytes("WEBP", (20, 30, 40)))

    downloader = FakeDownloader(tmp_path)
    product = ScrapedProduct(
        code=code,
        name="Producto de prueba",
        url="https://site.test/producto/fb-1507/",
        image_url="https://site.test/fb-1507.webp",
        image_path=f"data/images/products/{code}/{code}-01.webp",
    )
    product.image_candidates = [
        _candidate("https://site.test/fb-1507.webp", 1),
        _candidate("https://site.test/fb-1507-side.webp", 2),
    ]

    service = ProductGallerySyncService(
        browser=object(),
        product_extractor=object(),
        image_downloader=downloader,
        review_service=None,
        max_workers=1,
        max_candidates=6,
        refresh_existing=True,
    )

    synced = service.sync_products([product])[0]

    assert downloader.downloads == ["https://site.test/fb-1507-side.webp"]
    assert len(synced.gallery_images) == 2
    assert Path(module.resolve_data_path(synced.image_path)) == primary_path
    assert Path(
        module.resolve_data_path(synced.gallery_images[0]["image_path"])
    ) == primary_path
    assert [Path(image["image_path"]).name for image in synced.gallery_images] == [
        f"{code}-01.webp",
        f"{code}-02.webp",
    ]
    assert all(
        Path(module.resolve_data_path(image["image_path"])).parent == product_dir
        for image in synced.gallery_images
    )


def test_legacy_gallery_removes_primary_hash_duplicate_during_sync(
    monkeypatch,
    tmp_path,
):
    import hashlib

    import services.scraping.product_gallery_sync_service as module

    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: (
            Path(value)
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )
    monkeypatch.setattr(module, "IMAGE_PRODUCTS_DIR", Path("data/images/products"))

    code = "FB-1507"
    primary_url = "https://site.test/uploads/FB-1507-2.webp"
    scaled_url = "https://site.test/uploads/FB-1507-2-scaled.webp"
    alternate_url = "https://site.test/uploads/FB-1507.webp"

    primary_source = tmp_path / "data/images/products/FB-1507.webp"
    primary_source.parent.mkdir(parents=True)
    primary_image = image_bytes("WEBP", (20, 30, 40))
    primary_source.write_bytes(primary_image)

    gallery_root = tmp_path / "data/images/gallery/FB-1507"
    gallery_root.mkdir(parents=True)
    scaled_source = gallery_root / "FB-1507-01.webp"
    duplicate_source = gallery_root / "FB-1507-02.webp"
    alternate_source = gallery_root / "FB-1507-03.webp"
    scaled_source.write_bytes(image_bytes("WEBP", (50, 60, 70)))
    duplicate_source.write_bytes(primary_image)
    alternate_source.write_bytes(image_bytes("WEBP", (80, 90, 100)))

    existing = Product(
        code=code,
        name="Producto FB-1507",
        image_url=primary_url,
        image_path="data/images/products/FB-1507.webp",
        gallery_images=[
            {
                "url": scaled_url,
                "image_path": "data/images/gallery/FB-1507/FB-1507-01.webp",
                "position": 1,
                "source": "woocommerce-gallery",
            },
            {
                "url": primary_url,
                "image_path": "data/images/gallery/FB-1507/FB-1507-02.webp",
                "position": 2,
                "source": "woocommerce-gallery",
            },
            {
                "url": alternate_url,
                "image_path": "data/images/gallery/FB-1507/FB-1507-03.webp",
                "position": 3,
                "source": "woocommerce-gallery",
            },
        ],
    )
    repository = FakeRepository([existing])
    review = FakeReviewService(repository)

    product = ScrapedProduct(
        code=code,
        name="Producto FB-1507",
        url="https://site.test/producto/fb-1507/",
        image_url=primary_url,
        image_path="data/images/products/FB-1507.webp",
    )
    product.image_candidates = []

    service = ProductGallerySyncService(
        browser=object(),
        product_extractor=object(),
        image_downloader=FakeDownloader(tmp_path),
        review_service=review,
        max_workers=1,
        max_candidates=6,
        refresh_existing=False,
    )

    synced = service.sync_products([product])[0]

    assert [image["url"] for image in synced.gallery_images] == [
        primary_url,
        scaled_url,
        alternate_url,
    ]
    assert len(synced.gallery_images) == 3

    gallery_hashes = [
        hashlib.sha256(
            Path(module.resolve_data_path(image["image_path"])).read_bytes()
        ).hexdigest()
        for image in synced.gallery_images
    ]
    assert len(gallery_hashes) == len(set(gallery_hashes))
    assert Path(module.resolve_data_path(synced.image_path)) == Path(
        module.resolve_data_path(synced.gallery_images[0]["image_path"])
    )
    assert all(
        Path(module.resolve_data_path(image["image_path"])) != duplicate_source
        for image in synced.gallery_images
    )

    # Normalization removes the obsolete DB reference but leaves physical
    # deletion to the post-commit unused-image cleanup.
    assert duplicate_source.is_file()




def test_gallery_sync_drops_scaled_visual_duplicate_before_publishing(
    monkeypatch,
    tmp_path,
):
    from io import BytesIO

    from PIL import Image, ImageDraw

    import services.scraping.product_gallery_sync_service as module

    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: (
            Path(value)
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )
    monkeypatch.setattr(module, "IMAGE_PRODUCTS_DIR", Path("data/images/products"))

    code = "FB-1507"
    product_dir = tmp_path / "data" / "images" / "products" / code
    product_dir.mkdir(parents=True)
    primary_url = "https://site.test/uploads/FB-1507-2.webp"
    scaled_url = "https://site.test/uploads/FB-1507-2-scaled.webp"
    alternate_url = "https://site.test/uploads/FB-1507.webp"

    def pattern(size, color):
        image = Image.new("RGB", (size, size), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            (size // 12, size // 12, size * 11 // 12, size * 11 // 12),
            outline=color,
            width=max(size // 40, 1),
        )
        draw.ellipse(
            (size // 4, size // 4, size * 3 // 4, size * 3 // 4),
            fill=color,
        )
        draw.line(
            (size // 12, size // 2, size * 11 // 12, size // 2),
            fill="gold",
            width=max(size // 30, 1),
        )
        stream = BytesIO()
        image.save(stream, format="WEBP", quality=94, method=6)
        return stream.getvalue()

    primary_bytes = pattern(512, "royalblue")
    with Image.open(BytesIO(primary_bytes)) as original:
        scaled = original.resize((320, 320), Image.Resampling.LANCZOS)
        stream = BytesIO()
        scaled.save(stream, format="WEBP", quality=92, method=6)
        scaled_bytes = stream.getvalue()
    alternate_bytes = pattern(256, "crimson")

    primary_path = product_dir / f"{code}-01.webp"
    primary_path.write_bytes(primary_bytes)

    class MappedDownloader:
        def __init__(self):
            self.downloads = []

        def download_gallery(self, download_code, url, position, output_dir):
            directory = Path(output_dir)
            directory.mkdir(parents=True, exist_ok=True)
            destination = directory / f"{download_code}-{position:02d}.webp"
            payload = {
                scaled_url: scaled_bytes,
                alternate_url: alternate_bytes,
            }[url]
            destination.write_bytes(payload)
            self.downloads.append(url)
            return str(destination.relative_to(tmp_path)).replace("\\", "/")

    downloader = MappedDownloader()
    product = ScrapedProduct(
        code=code,
        name="Producto FB-1507",
        url="https://site.test/producto/fb-1507/",
        image_url=primary_url,
        image_path=f"data/images/products/{code}/{code}-01.webp",
        image_hash=hashlib.sha256(primary_bytes).hexdigest(),
    )
    product.image_candidates = [
        _candidate(primary_url, 1),
        _candidate(scaled_url, 2),
        _candidate(alternate_url, 3),
    ]

    service = ProductGallerySyncService(
        browser=object(),
        product_extractor=object(),
        image_downloader=downloader,
        review_service=None,
        max_workers=1,
        max_candidates=2,
        refresh_existing=True,
    )

    synced = service.sync_products([product])[0]

    assert downloader.downloads == [scaled_url, alternate_url]
    assert [item["url"] for item in synced.gallery_images] == [
        primary_url,
        alternate_url,
    ]
    assert [item["position"] for item in synced.gallery_images] == [1, 2]
    assert Path(module.resolve_data_path(synced.image_path)) == primary_path
    assert len(list(product_dir.glob("*.webp"))) == 2
    assert not (product_dir / f"{code}-03.webp").exists()


def test_gallery_sync_keeps_all_page_candidates_beyond_review_limit(
    monkeypatch,
    tmp_path,
):
    import services.scraping.product_gallery_sync_service as module

    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: (
            Path(value)
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )
    monkeypatch.setattr(module, "IMAGE_PRODUCTS_DIR", Path("data/images/products"))

    code = "P-ALL-IMAGES"
    product_dir = tmp_path / "data" / "images" / "products" / code
    product_dir.mkdir(parents=True)
    primary_url = f"https://site.test/uploads/{code}.webp"
    primary_path = product_dir / f"{code}-01.webp"
    primary_bytes = image_bytes("WEBP", (10, 20, 30))
    primary_path.write_bytes(primary_bytes)

    existing = Product(
        code=code,
        name="Producto de prueba",
        image_url=primary_url,
        image_path=f"data/images/products/{code}/{code}-01.webp",
        image_hash=hashlib.sha256(primary_bytes).hexdigest(),
        gallery_images=[
            {
                "url": primary_url,
                "image_path": f"data/images/products/{code}/{code}-01.webp",
                "image_hash": hashlib.sha256(primary_bytes).hexdigest(),
                "position": 1,
                "source": "primary",
            }
        ],
    )
    repository = FakeRepository([existing])
    review = FakeReviewService(repository)
    downloader = FakeDownloader(tmp_path)
    product = ScrapedProduct(
        code=code,
        name="Producto de prueba",
        url="https://site.test/producto/p-all-images/",
        image_url=primary_url,
        image_path=f"data/images/products/{code}/{code}-01.webp",
        image_hash=hashlib.sha256(primary_bytes).hexdigest(),
    )
    urls = [
        primary_url,
        *[
            f"https://site.test/uploads/{code}-alt-{index:02d}.webp"
            for index in range(2, 9)
        ],
    ]
    product.image_candidates = [
        _candidate(url, position)
        for position, url in enumerate(urls, start=1)
    ]

    service = ProductGallerySyncService(
        browser=object(),
        product_extractor=object(),
        image_downloader=downloader,
        review_service=review,
        max_workers=1,
        max_candidates=2,
        refresh_existing=False,
    )

    synced = service.sync_products([product])[0]

    assert len(synced.gallery_images) == 8
    assert [image["url"] for image in synced.gallery_images] == urls
    assert downloader.downloads == urls[1:]
    assert len(review.registered) == 1
    assert len(review.registered[0]["candidate_options"]) == 2



def test_incomplete_gallery_refresh_preserves_last_complete_images(
    monkeypatch,
    tmp_path,
):
    import services.scraping.product_gallery_sync_service as module

    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: (
            Path(value)
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )
    monkeypatch.setattr(
        module,
        "IMAGE_PRODUCTS_DIR",
        Path("data/images/products"),
    )

    code = "P-KEEP-GALLERY"
    product_dir = tmp_path / "data" / "images" / "products" / code
    product_dir.mkdir(parents=True)
    primary_url = f"https://site.test/uploads/{code}.webp"
    alternate_url = f"https://site.test/uploads/{code}-alt.webp"
    failed_url = f"https://site.test/uploads/{code}-new.webp"

    primary_path = product_dir / f"{code}-01.webp"
    alternate_path = product_dir / f"{code}-02.webp"
    primary_path.write_bytes(image_bytes("WEBP", (10, 20, 30)))
    alternate_path.write_bytes(image_bytes("WEBP", (90, 80, 70)))

    existing = Product(
        code=code,
        name="Producto con galería válida",
        image_url=primary_url,
        image_path=f"data/images/products/{code}/{code}-01.webp",
        image_hash=hashlib.sha256(primary_path.read_bytes()).hexdigest(),
        gallery_images=[
            {
                "url": primary_url,
                "image_path": f"data/images/products/{code}/{code}-01.webp",
                "image_hash": hashlib.sha256(primary_path.read_bytes()).hexdigest(),
                "position": 1,
                "source": "primary",
            },
            {
                "url": alternate_url,
                "image_path": f"data/images/products/{code}/{code}-02.webp",
                "image_hash": hashlib.sha256(alternate_path.read_bytes()).hexdigest(),
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )
    repository = FakeRepository([existing])

    class PartiallyFailingDownloader(FakeDownloader):
        def download_gallery(self, download_code, url, position, output_dir):
            if url == failed_url:
                self.downloads.append(url)
                raise OSError("simulated image download failure")
            return super().download_gallery(
                download_code, url, position, output_dir
            )

    downloader = PartiallyFailingDownloader(tmp_path)
    product = ScrapedProduct(
        code=code,
        name="Producto con galería válida",
        url=f"https://site.test/producto/{code.casefold()}/",
        image_url=primary_url,
        image_path=f"data/images/products/{code}/{code}-01.webp",
        image_hash=existing.image_hash,
    )
    product.image_candidates = [
        _candidate(primary_url, 1),
        _candidate(alternate_url, 2),
        _candidate(failed_url, 3),
    ]

    service = ProductGallerySyncService(
        browser=object(),
        product_extractor=object(),
        image_downloader=downloader,
        review_service=FakeReviewService(repository),
        max_workers=1,
        max_candidates=6,
        refresh_existing=False,
    )

    synced = service.sync_products([product])[0]

    assert downloader.downloads == [failed_url]
    assert synced.image_url == primary_url
    assert synced.image_path == f"data/images/products/{code}/{code}-01.webp"
    assert synced.image_hash == existing.image_hash
    assert [image["url"] for image in synced.gallery_images] == [
        primary_url,
        alternate_url,
    ]
    assert [image["image_path"] for image in synced.gallery_images] == [
        f"data/images/products/{code}/{code}-01.webp",
        f"data/images/products/{code}/{code}-02.webp",
    ]
    assert [image["position"] for image in synced.gallery_images] == [1, 2]
    assert primary_path.is_file()
    assert alternate_path.is_file()
    assert not (product_dir / f"{code}-03.webp").exists()

def test_fb4047_revalidates_live_page_instead_of_reusing_cached_detail_candidates():
    from types import SimpleNamespace

    primary_url = "https://site.test/wp-content/uploads/FOCO-ANTIESTRES.webp"
    third_url = (
        "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
        "MEZCLADOR-CAMION-copia.webp"
    )
    detail_url = "https://stock.importacionesfacundo.com/producto/foco-antiestres/"

    class FreshBrowser:
        def __init__(self):
            self.calls = []

        def get(self, url, *, force_revalidate=False):
            self.calls.append((url, force_revalidate))
            assert force_revalidate is True
            return "<html><body>respuesta viva</body></html>"

    class FreshPageExtractor:
        def extract(self, soup, *, url, category):
            assert "respuesta viva" in soup.get_text()
            return SimpleNamespace(
                code="FB-4047",
                name="Foco Antiestrés",
                image_candidates=[
                    {
                        **_candidate(primary_url, 1),
                        "gallery_container": True,
                    },
                    {
                        **_candidate(third_url, 2),
                        "gallery_container": True,
                    },
                ],
            )

    browser = FreshBrowser()
    existing = Product(
        code="FB-4047",
        name="Foco Antiestrés",
        image_url=primary_url,
        gallery_images=[
            {
                "url": primary_url,
                "image_path": "data/images/products/FB-4047/FB-4047-01.webp",
                "image_hash": "primary-hash",
                "position": 1,
                "source": "woocommerce-gallery",
            },
            {
                "url": "https://site.test/known-second.webp",
                "image_path": "data/images/products/FB-4047/FB-4047-02.webp",
                "image_hash": "second-hash",
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )
    product = ScrapedProduct(
        code="FB-4047",
        name="Foco Antiestrés",
        url=detail_url,
        image_url=primary_url,
    )
    product.image_candidates = [
        _candidate(primary_url, 1),
        _candidate("https://site.test/stale-candidate.webp", 2),
    ]
    product.image_candidates_source = "detail"

    service = ProductGallerySyncService(
        browser=browser,
        product_extractor=FreshPageExtractor(),
        image_downloader=object(),
        refresh_existing=True,
    )

    candidates = service._candidate_source(product, existing)

    assert browser.calls == [(detail_url, True)]
    assert [candidate["url"] for candidate in candidates] == [
        primary_url,
        third_url,
    ]
    assert product.image_candidates_source == "detail"

def test_fb4047_valid_live_gallery_does_not_restore_absent_historical_url():
    from types import SimpleNamespace

    primary_url = "https://site.test/uploads/FB-4047-main.webp"
    second_url = "https://site.test/uploads/FB-4047-second.webp"
    recovered_url = (
        "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
        "MEZCLADOR-CAMION-copia.webp"
    )
    detail_url = "https://stock.importacionesfacundo.com/producto/foco-antiestres/"

    class FreshBrowser:
        def __init__(self):
            self.calls = []

        def get(self, url, *, force_revalidate=False):
            self.calls.append((url, force_revalidate))
            assert force_revalidate is True
            return "<html><body>ficha real del producto</body></html>"

    class LiveExtractor:
        def extract(self, soup, *, url, category):
            assert "ficha real del producto" in soup.get_text()
            return SimpleNamespace(
                code="FB-4047",
                name="Foco Antiestrés",
                image_candidates=[
                    {
                        **_candidate(primary_url, 1),
                        "gallery_container": True,
                    },
                    {
                        **_candidate(second_url, 2),
                        "gallery_container": True,
                    },
                ],
            )

    browser = FreshBrowser()
    existing = Product(
        code="FB-4047",
        name="Foco Antiestrés",
        image_url=primary_url,
        gallery_images=[
            {
                "url": primary_url,
                "image_path": "data/images/products/FB-4047/FB-4047-01.webp",
                "image_hash": "primary-hash",
                "position": 1,
                "source": "primary",
            },
            {
                "url": second_url,
                "image_path": "data/images/products/FB-4047/FB-4047-02.webp",
                "image_hash": "second-hash",
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )
    product = ScrapedProduct(
        code="FB-4047",
        name="Foco Antiestrés",
        url=detail_url,
        image_url=primary_url,
    )
    product.image_candidates = [
        _candidate(primary_url, 1),
        _candidate("https://site.test/uploads/stale-cached-image.webp", 2),
    ]
    product.image_candidates_source = "detail"

    service = ProductGallerySyncService(
        browser=browser,
        product_extractor=LiveExtractor(),
        image_downloader=object(),
        refresh_existing=True,
    )

    candidates = service._candidate_source(product, existing)

    assert browser.calls == [(detail_url, True)]
    assert [candidate["url"] for candidate in candidates] == [
        primary_url,
        second_url,
    ]
    assert recovered_url not in [candidate["url"] for candidate in candidates]


def test_fb4047_recovery_hash_mismatch_preserves_existing_gallery(
    monkeypatch,
    tmp_path,
):
    import services.scraping.product_gallery_sync_service as module
    from scrapers.images.image_downloader import ImageDownloader

    monkeypatch.setattr(
        module,
        "resolve_data_path",
        lambda value: (
            Path(value)
            if Path(value).is_absolute()
            else tmp_path / value
        ),
    )
    monkeypatch.setattr(
        module,
        "IMAGE_PRODUCTS_DIR",
        Path("data/images/products"),
    )

    code = "FB-4047"
    primary_url = "https://site.test/uploads/FB-4047-main.webp"
    second_url = "https://site.test/uploads/FB-4047-second.webp"
    recovered_url = (
        "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
        "MEZCLADOR-CAMION-copia.webp"
    )
    detail_url = "https://stock.importacionesfacundo.com/producto/foco-antiestres/"
    product_dir = tmp_path / "data/images/products" / code
    product_dir.mkdir(parents=True)
    primary_path = product_dir / f"{code}-01.webp"
    second_path = product_dir / f"{code}-02.webp"
    primary_path.write_bytes(image_bytes("WEBP", (20, 30, 40)))
    second_path.write_bytes(image_bytes("WEBP", (50, 60, 70)))
    primary_hash = ImageDownloader.hash_file(primary_path)
    second_hash = ImageDownloader.hash_file(second_path)

    existing = Product(
        code=code,
        name="Foco Antiestrés",
        image_url=primary_url,
        image_path=f"data/images/products/{code}/{code}-01.webp",
        image_hash=primary_hash,
        gallery_images=[
            {
                "url": primary_url,
                "image_path": f"data/images/products/{code}/{code}-01.webp",
                "image_hash": primary_hash,
                "position": 1,
                "source": "primary",
            },
            {
                "url": second_url,
                "image_path": f"data/images/products/{code}/{code}-02.webp",
                "image_hash": second_hash,
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )

    class GatedBrowser:
        def get_uncached(self, url):
            assert url == detail_url
            return (
                "<html><h1>Acceso Exclusivo para Distribuidores</h1>"
                "<span class='sku'>FB-4047</span></html>"
            )

    class GatedExtractor:
        def extract(self, soup, *, url, category):
            assert "Acceso Exclusivo para Distribuidores" in soup.get_text()
            return type(
                "ExtractedPage",
                (),
                {
                    "code": code,
                    "name": "Acceso Exclusivo para Distribuidores",
                    "image_candidates": [],
                },
            )()

    product = ScrapedProduct(
        code=code,
        name="Foco Antiestrés",
        url=detail_url,
        image_url=primary_url,
        image_path=f"data/images/products/{code}/{code}-01.webp",
        image_hash=primary_hash,
    )
    product.image_candidates = [
        _candidate(primary_url, 1),
        _candidate(second_url, 2),
    ]
    product.image_candidates_source = "detail"
    downloader = FakeDownloader(tmp_path)
    service = ProductGallerySyncService(
        browser=GatedBrowser(),
        product_extractor=GatedExtractor(),
        image_downloader=downloader,
        refresh_existing=True,
    )

    synced = service._sync_product(product, existing)

    assert downloader.downloads == [recovered_url]
    assert synced.image_url == primary_url
    assert synced.image_path == existing.image_path
    assert synced.image_hash == primary_hash
    assert [image["url"] for image in synced.gallery_images] == [
        primary_url,
        second_url,
    ]
    assert primary_path.is_file()
    assert second_path.is_file()
    assert not (product_dir / f"{code}-03.webp").exists()


def test_fb4047_recovers_verified_gallery_when_live_page_returns_access_gate():
    from types import SimpleNamespace

    primary_url = "https://site.test/uploads/SFPU-38.webp"
    second_url = "https://site.test/uploads/FOCO-AMARILLO.webp"
    recovered_url = (
        "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
        "MEZCLADOR-CAMION-copia.webp"
    )
    detail_url = "https://stock.importacionesfacundo.com/producto/foco-antiestres/"

    class GatedBrowser:
        def __init__(self):
            self.calls = []

        def get_uncached(self, url):
            self.calls.append((url, "uncached"))
            return (
                "<html><h1>Acceso Exclusivo para Distribuidores</h1>"
                "<span class='sku'>FB-4047</span></html>"
            )

    class GatedExtractor:
        def extract(self, soup, *, url, category):
            assert "Acceso Exclusivo para Distribuidores" in soup.get_text()
            return SimpleNamespace(
                code="FB-4047",
                name="Acceso Exclusivo para Distribuidores",
                image_candidates=[],
            )

    browser = GatedBrowser()
    existing = Product(
        code="FB-4047",
        name="Foco Antiestrés",
        image_url=primary_url,
        gallery_images=[
            {
                "url": primary_url,
                "image_path": "data/images/products/FB-4047/FB-4047-01.webp",
                "image_hash": "primary-hash",
                "position": 1,
                "source": "primary",
            },
            {
                "url": second_url,
                "image_path": "data/images/products/FB-4047/FB-4047-02.webp",
                "image_hash": "second-hash",
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )
    product = ScrapedProduct(
        code="FB-4047",
        name="Foco Antiestrés",
        url=detail_url,
        image_url=primary_url,
    )
    product.image_candidates = [
        _candidate(primary_url, 1),
        _candidate(second_url, 2),
    ]
    product.image_candidates_source = "detail"

    service = ProductGallerySyncService(
        browser=browser,
        product_extractor=GatedExtractor(),
        image_downloader=object(),
        refresh_existing=True,
    )

    candidates = service._candidate_source(product, existing)

    assert browser.calls == [(detail_url, "uncached")]
    assert [candidate["url"] for candidate in candidates] == [
        primary_url,
        second_url,
        recovered_url,
    ]
    assert candidates[-1]["source"] == "verified-historical-gallery-recovery"


def test_fb4047_uses_corroborated_live_gallery_when_title_is_access_gate():
    from types import SimpleNamespace

    primary_url = (
        "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
        "SFPU-38.webp"
    )
    second_url = (
        "https://stock.importacionesfacundo.com/wp-content/uploads/2024/05/"
        "FOCO-AMARILLO.webp"
    )
    third_url = (
        "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
        "MEZCLADOR-CAMION-copia.webp"
    )
    detail_url = "https://stock.importacionesfacundo.com/producto/foco-antiestres/"
    detail_description = (
        "Material: Poliuretano. Dimensiones: 55*55*100mm. Peso Unitario: 24 G. "
        "Uso Recomendado: Antiestrés, Promocional. Empaque Individual: Bolsa de "
        "polietileno. Cantidad Por Caja: 250 Pza. Dimensiones Caja: 60*33*32cm. "
        "Cubicaje por Caja: 0.0634 m³/CBM Peso neto por caja: 7.5 Kg. "
        "Peso bruto por caja: 8.5 Kg."
    )

    class LiveBrowser:
        def __init__(self):
            self.calls = []

        def get_uncached(self, url):
            self.calls.append(url)
            return "<html><body>HTML de FB-4047 con galería</body></html>"

    class LiveExtractor:
        def extract(self, soup, *, url, category):
            assert "HTML de FB-4047 con galería" in soup.get_text()
            return SimpleNamespace(
                code="FB-4047",
                name="Acceso Exclusivo para Distribuidores",
                description=detail_description,
                image_candidates=[
                    {**_candidate(primary_url, 1), "gallery_container": True},
                    {**_candidate(second_url, 2), "gallery_container": True},
                    {**_candidate(third_url, 3), "gallery_container": True},
                ],
            )

    browser = LiveBrowser()
    existing = Product(
        code="FB-4047",
        name="Foco Antiestrés",
        description=detail_description,
        image_url=primary_url,
        gallery_images=[
            {
                "url": primary_url,
                "image_path": "data/images/products/FB-4047/FB-4047-01.webp",
                "image_hash": "primary-hash",
                "position": 1,
                "source": "woocommerce-gallery",
            },
            {
                "url": second_url,
                "image_path": "data/images/products/FB-4047/FB-4047-02.webp",
                "image_hash": "second-hash",
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )
    product = ScrapedProduct(
        code="FB-4047",
        name="Foco Antiestrés",
        description=detail_description,
        url=detail_url,
        image_url=primary_url,
    )
    product.image_candidates = [
        _candidate(primary_url, 1),
        _candidate("https://site.test/stale-candidate.webp", 2),
    ]
    product.image_candidates_source = "detail"

    service = ProductGallerySyncService(
        browser=browser,
        product_extractor=LiveExtractor(),
        image_downloader=object(),
        refresh_existing=True,
    )

    candidates = service._candidate_source(product, existing)

    assert browser.calls == [detail_url]
    assert [candidate["url"] for candidate in candidates] == [
        primary_url,
        second_url,
        third_url,
    ]
    assert product.image_candidates_source == "detail"
    assert product.image_url == primary_url
