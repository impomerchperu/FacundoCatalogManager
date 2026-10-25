from pathlib import Path

from scrapers.images.image_hash import ImageHash
from scrapers.images.product_image_storage import store_image_in_product_group
from tests.scraping.image_test_utils import image_bytes


def test_legacy_image_is_copied_into_canonical_product_group(tmp_path: Path):
    root = tmp_path / "data" / "images" / "products"
    legacy = root / "FB-1507.webp"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(image_bytes("WEBP", (1, 2, 3)))

    stored_path, stored_hash = store_image_in_product_group(
        "FB-1507",
        legacy,
        1,
        root=root,
    )

    expected = root / "FB-1507" / "FB-1507-01.webp"
    assert Path(stored_path) == expected
    assert expected.read_bytes() == legacy.read_bytes()
    assert stored_hash == ImageHash().calculate(expected)
    assert legacy.is_file()


def test_product_group_storage_never_overwrites_different_alternative(
    tmp_path: Path,
):
    root = tmp_path / "data" / "images" / "products"
    source_dir = tmp_path / "legacy"
    source_dir.mkdir()
    first = source_dir / "first.webp"
    second = source_dir / "second.webp"
    first.write_bytes(image_bytes("WEBP", (4, 5, 6)))
    second.write_bytes(image_bytes("WEBP", (7, 8, 9)))

    first_path, first_hash = store_image_in_product_group(
        "FB-1507",
        first,
        2,
        root=root,
    )
    second_path, second_hash = store_image_in_product_group(
        "FB-1507",
        second,
        2,
        root=root,
    )

    assert Path(first_path).is_file()
    assert Path(second_path).is_file()
    assert Path(first_path) != Path(second_path)
    assert Path(first_path).read_bytes() == first.read_bytes()
    assert Path(second_path).read_bytes() == second.read_bytes()
    assert first_hash != second_hash
    assert first.is_file()
    assert second.is_file()


def test_identical_image_reuses_existing_file_in_the_same_product_group(
    tmp_path: Path,
):
    root = tmp_path / "data" / "images" / "products"
    source_dir = tmp_path / "legacy"
    source_dir.mkdir()
    primary = source_dir / "primary.webp"
    duplicate = source_dir / "duplicate.webp"
    primary.write_bytes(image_bytes("WEBP", (10, 11, 12)))
    duplicate.write_bytes(image_bytes("WEBP", (10, 11, 12)))

    primary_path, primary_hash = store_image_in_product_group(
        "FB-1507",
        primary,
        1,
        root=root,
    )
    duplicate_path, duplicate_hash = store_image_in_product_group(
        "FB-1507",
        duplicate,
        2,
        root=root,
    )

    product_dir = root / "FB-1507"
    assert duplicate_path == primary_path
    assert duplicate_hash == primary_hash
    assert len(list(product_dir.iterdir())) == 1
    assert primary.is_file()
    assert duplicate.is_file()


def test_canonical_group_normalization_can_skip_redundant_sibling_scan(
    tmp_path: Path,
    monkeypatch,
):
    import scrapers.images.product_image_storage as storage_module

    root = tmp_path / "data" / "images" / "products"
    product_dir = root / "FB-1507"
    product_dir.mkdir(parents=True)
    canonical = product_dir / "FB-1507-01.webp"
    sibling = product_dir / "FB-1507-02.webp"
    payload = image_bytes("WEBP", (10, 11, 12))
    canonical.write_bytes(payload)
    sibling.write_bytes(payload)

    def fail_if_scanned(*args, **kwargs):
        raise AssertionError("Canonical normalization should not rescan sibling files.")

    monkeypatch.setattr(
        storage_module,
        "_find_matching_image",
        fail_if_scanned,
    )

    stored_path, stored_hash = store_image_in_product_group(
        "FB-1507",
        canonical,
        1,
        root=root,
        deduplicate_in_group=False,
    )

    assert Path(stored_path) == canonical
    assert stored_hash == ImageHash().calculate(canonical)
    assert sibling.is_file()


def test_product_group_storage_corrects_a_mislabeled_legacy_image(
    tmp_path: Path,
):
    root = tmp_path / "data" / "images" / "products"
    legacy_dir = tmp_path / "data" / "images" / "legacy"
    legacy_dir.mkdir(parents=True)
    legacy = legacy_dir / "SKB05J4.webp"
    payload = image_bytes("PNG", (23, 45, 67))
    legacy.write_bytes(payload)

    stored_path, stored_hash = store_image_in_product_group(
        "SKB05J4",
        legacy,
        1,
        root=root,
    )

    canonical = Path(stored_path)
    assert canonical.name == "SKB05J4-01.png"
    assert canonical.read_bytes() == payload
    assert stored_hash == ImageHash().calculate(canonical)
    assert legacy.is_file()
    assert legacy.suffix == ".webp"


def test_product_group_storage_rejects_unidentifiable_content(
    tmp_path: Path,
):
    root = tmp_path / "data" / "images" / "products"
    source = tmp_path / "legacy" / "FB-9999.webp"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not a raster image")

    stored_path, stored_hash = store_image_in_product_group(
        "FB-9999",
        source,
        1,
        root=root,
    )

    assert stored_path == ""
    assert stored_hash == ""
    assert source.is_file()
    assert not (root / "FB-9999").exists()
