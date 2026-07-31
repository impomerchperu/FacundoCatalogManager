from services.scraping.image_sync_service import ImageSyncService
from services.scraping.sync_repository import SyncRepository
from models.scraping.image_record import ImageRecord


def test_image_sync_downloads_new_image():

    class FakeBrowser:

        def get(self, url):

            return b"image-data"


    service = ImageSyncService(
        SyncRepository(),
        None
    )


    product = {
        "code": "P001",
        "image": "image.jpg"
    }


    result = service.sync(
        product,
        FakeBrowser()
    )


    assert result is True



def test_image_sync_skips_existing_image():

    class FakeBrowser:

        def get(self, url):

            raise Exception(
                "No debe descargar"
            )


    repository = SyncRepository()


    repository.save(
        ImageRecord(
            code="P001",
            image_url="image.jpg",
            image_path="P001.jpg",
            checksum="abc"
        )
    )


    service = ImageSyncService(
        repository,
        None
    )


    product = {
        "code": "P001",
        "image": "image.jpg"
    }


    result = service.sync(
        product,
        FakeBrowser()
    )


    assert result is False