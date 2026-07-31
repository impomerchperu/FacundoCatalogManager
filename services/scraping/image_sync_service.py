import hashlib

from models.scraping.image_record import ImageRecord


class ImageSyncService:

    def __init__(
        self,
        repository,
        downloader
    ):

        self.repository = repository
        self.downloader = downloader


    def calculate_hash(
        self,
        content
    ):

        return hashlib.md5(
            content
        ).hexdigest()


    def needs_update(
        self,
        product
    ):

        current = self.repository.get(
            product["code"]
        )


        if current is None:
            return True


        return (
            current.image_url != product["image"]
        )


    def sync(
        self,
        product,
        browser
    ):

        if not self.needs_update(
            product
        ):
            return False


        content = browser.get(
            product["image"]
        )


        checksum = self.calculate_hash(
            content
        )


        record = ImageRecord(
            code=product["code"],
            image_url=product["image"],
            image_path="",
            checksum=checksum
        )


        self.repository.save(
            record
        )


        return True