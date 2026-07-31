from models.scraping.image_record import ImageRecord
from services.scraping.image_sync_service import ImageSyncService
from services.scraping.sync_repository import SyncRepository


def test_image_sync_downloads_new_image():

    class FakeBrowser:
        def get(self, url):

            return b"image-data"

    service = ImageSyncService(SyncRepository(), None)

    product = {"code": "P001", "image": "image.jpg"}

    result = service.sync(product, FakeBrowser())

    assert result is True


def test_image_sync_skips_existing_image():

    class FakeBrowser:
        def get(self, url):

            raise Exception("No debe descargar")

    repository = SyncRepository()

    repository.save(
        ImageRecord(
            code="P001", image_url="image.jpg", image_path="P001.jpg", checksum="abc"
        )
    )

    service = ImageSyncService(repository, None)

    product = {"code": "P001", "image": "image.jpg"}

    result = service.sync(product, FakeBrowser())

    assert result is False


def test_image_sync_updates_changed_image():

    class FakeBrowser:
        def get(self, url):

            return b"new-image-data"

    repository = SyncRepository()

    repository.save(
        ImageRecord(
            code="P001",
            image_url="old-image.jpg",
            image_path="P001.jpg",
            checksum="old-checksum",
        )
    )

    service = ImageSyncService(repository, None)

    product = {"code": "P001", "image": "new-image.jpg"}

    result = service.sync(product, FakeBrowser())

    assert result is True

    updated = repository.get("P001")

    assert updated.image_url == "new-image.jpg"

    assert updated.checksum != "old-checksum"
