from PIL import Image

from scrapers.images.image_validator import ImageValidator


def test_image_validator_accepts_valid_image(tmp_path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), (255, 0, 0)).save(image_path, format="PNG")

    assert ImageValidator().validate(str(image_path)) is True


def test_image_validator_rejects_missing_image(tmp_path):
    missing = tmp_path / "no-existe.webp"

    assert ImageValidator().validate(str(missing)) is False
