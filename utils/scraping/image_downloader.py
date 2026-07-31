from pathlib import Path

from utils.scraping.image_validator import ImageValidator


class ImageDownloader:

    def __init__(
        self,
        output_folder="images",
        validator=None
    ):

        self.output_folder = Path(
            output_folder
        )

        self.output_folder.mkdir(
            exist_ok=True
        )

        self.validator = (
            validator
            or ImageValidator()
        )


    def download(
        self,
        code,
        image_url,
        downloader
    ):

        filename = (
            self.output_folder /
            f"{code}.jpg"
        )


        if filename.exists():
            return str(filename)


        content = downloader.get(
            image_url
        )


        if not self.validator.is_valid_content(
            content
        ):
            return None


        filename.write_bytes(
            content
        )


        return str(filename)