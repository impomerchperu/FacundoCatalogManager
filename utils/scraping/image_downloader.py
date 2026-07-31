from pathlib import Path


class ImageDownloader:

    def __init__(
        self,
        output_folder="images"
    ):

        self.output_folder = Path(
            output_folder
        )

        self.output_folder.mkdir(
            parents=True,
            exist_ok=True
        )


    def download(
        self,
        code,
        image_url,
        downloader
    ):

        if not image_url:

            return None


        filename = (
            self.output_folder /
            f"{code}.jpg"
        )


        if filename.exists():

            return str(filename)


        try:

            content = downloader.get(
                image_url
            )

            filename.write_bytes(
                content
            )

        except Exception:

            return None


        return str(filename)