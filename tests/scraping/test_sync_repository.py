from models.scraping.image_record import ImageRecord
from services.scraping.sync_repository import SyncRepository


def test_sync_repository_save_and_get():

    repository = SyncRepository()

    record = ImageRecord(
        code="P001", image_url="image.jpg", image_path="P001.jpg", checksum="123"
    )

    repository.save(record)

    result = repository.get("P001")

    assert result == record
