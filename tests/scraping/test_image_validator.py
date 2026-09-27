from pathlib import Path

from PIL import Image

from scrapers.images.image_validator import ImageValidator


def test_valid_jpg_extension():
    validator = ImageValidator()
    assert validator.is_valid_extension("P001.jpg")


def test_invalid_extension():
    validator = ImageValidator()
    assert not validator.is_valid_extension("P001.txt")


def test_valid_image_content():
    validator = ImageValidator()
    assert validator.is_valid_content(b"\xff\xd8fake")


def test_invalid_content():
    validator = ImageValidator()
    assert not validator.is_valid_content(b"hello")


def test_image_validator_accepts_valid_image(tmp_path: Path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), (255, 0, 0)).save(image_path, format="PNG")

    assert ImageValidator().validate(str(image_path)) is True


def test_image_validator_rejects_missing_image(tmp_path: Path):
    assert ImageValidator().validate(str(tmp_path / "no-existe.webp")) is False


def test_image_validator_accepts_valid_gif_file(tmp_path: Path):
    image_path = tmp_path / "sample.gif"
    Image.new("RGB", (8, 8), (255, 0, 0)).save(image_path, format="GIF")

    assert ImageValidator().validate(str(image_path)) is True
