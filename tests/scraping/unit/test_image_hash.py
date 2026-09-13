from PIL import Image

from scrapers.images.image_hash import ImageHash


def test_image_hash_calculates_sha256_for_existing_image(tmp_path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), (255, 0, 0)).save(image_path, format="PNG")

    hash_value = ImageHash().calculate(str(image_path))

    assert hash_value
    assert len(hash_value) == 64


def test_image_hash_returns_empty_string_for_missing_image(tmp_path):
    missing = tmp_path / "no-existe.webp"

    assert ImageHash().calculate(str(missing)) == ""
