from models.scraping.image_record import ImageRecord


def test_image_record_creation():

    record = ImageRecord(
        code="P001",
        image_url="image.jpg",
        image_path="images/P001.jpg",
        checksum="abc123"
    )

    assert record.code == "P001"
    assert record.image_url == "image.jpg"
    assert record.image_path == "images/P001.jpg"
    assert record.checksum == "abc123"