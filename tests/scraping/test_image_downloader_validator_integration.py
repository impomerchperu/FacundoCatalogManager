from pathlib import Path

from scrapers.images.image_validator import ImageValidator


def test_image_validator_rejects_invalid_image_file(tmp_path):
    image_path = Path(tmp_path) / "P001.jpg"
    image_path.write_bytes(b"invalid-data")

    validator = ImageValidator()

    assert validator.validate(str(image_path)) is False


def test_image_validator_accepts_valid_jpeg_file(tmp_path):
    image_path = Path(tmp_path) / "P002.jpg"
    image_path.write_bytes(
        b"\xff\xd8\xff\xe0" + b"0" * 32 + b"\xff\xd9"
    )

    validator = ImageValidator()

    assert validator.is_valid_extension(image_path.name) is True
    assert validator.is_valid_content(image_path.read_bytes()) is True
