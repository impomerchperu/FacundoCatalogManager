from pathlib import Path

import scrapers.images.image_repository as image_repository_module
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_repository import ImageRepository
from tests.scraping.image_test_utils import image_bytes


def test_find_path_repairs_identifiable_image_with_wrong_extension(
    tmp_path: Path,
    monkeypatch,
):
    data_root = tmp_path / "data"
    products_root = data_root / "images" / "products"
    products_root.mkdir(parents=True)
    legacy = products_root / "SKB05J4.webp"
    payload = image_bytes("PNG", (23, 45, 67))
    legacy.write_bytes(payload)

    monkeypatch.setattr(image_repository_module, "DATA_DIR", data_root)
    repository = ImageRepository(output_dir=products_root)

    result = repository.find_path(str(legacy))

    assert result is not None
    canonical = Path(result["image_path"])
    assert canonical == products_root / "SKB05J4" / "SKB05J4-01.png"
    assert canonical.is_file()
    assert canonical.read_bytes() == payload
    assert result["image_hash"] == ImageDownloader.verify_image_file(canonical)["image_hash"]
    assert legacy.is_file()


def test_find_path_rejects_unidentifiable_referenced_file(
    tmp_path: Path,
    monkeypatch,
):
    data_root = tmp_path / "data"
    products_root = data_root / "images" / "products"
    products_root.mkdir(parents=True)
    corrupt = products_root / "FB-9999.webp"
    corrupt.write_bytes(b"not an identifiable image")

    monkeypatch.setattr(image_repository_module, "DATA_DIR", data_root)
    repository = ImageRepository(output_dir=products_root)

    assert repository.find_path(str(corrupt)) is None
