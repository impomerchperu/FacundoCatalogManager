from utils.scraping.image_validator import ImageValidator


def test_valid_jpg_extension():

    validator = ImageValidator()

    assert validator.is_valid_extension(
        "P001.jpg"
    )


def test_invalid_extension():

    validator = ImageValidator()

    assert not validator.is_valid_extension(
        "P001.txt"
    )


def test_valid_image_content():

    validator = ImageValidator()

    content = b"\xff\xd8fake"

    assert validator.is_valid_content(
        content
    )


def test_invalid_content():

    validator = ImageValidator()

    assert not validator.is_valid_content(
        b"hello"
    )