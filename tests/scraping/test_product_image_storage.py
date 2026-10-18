from pathlib import Path

from scrapers.images.image_hash import ImageHash
from scrapers.images.product_image_storage import store_image_in_product_group


def test_legacy_image_is_copied_into_canonical_product_group(tmp_path: Path):
    root = tmp_path / "data" / "images" / "products"
    legacy = root / "FB-1507.webp"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"same-primary-image")

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
    first.write_bytes(b"first-image")
    second.write_bytes(b"second-image")

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
    assert Path(first_path).read_bytes() == b"first-image"
    assert Path(second_path).read_bytes() == b"second-image"
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
    primary.write_bytes(b"identical-image")
    duplicate.write_bytes(b"identical-image")

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
