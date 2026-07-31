from utils.scraping.image_downloader import ImageDownloader


class ImageDownloadManager:

    def __init__(
        self,
        image_downloader,
        image_validator
    ):

        self.image_downloader = image_downloader
        self.image_validator = image_validator


    def download_all(
        self,
        products,
        downloader
    ):

        results = []

        for product in products:

            code = product.get(
                "code"
            )

            image_url = product.get(
                "image"
            )


            if not code or not image_url:
                continue


            try:

                image_path = self.image_downloader.download(
                    code,
                    image_url,
                    downloader
                )


                if self.image_validator.is_valid(
                    image_path
                ):

                    product["image_path"] = image_path

                    results.append(
                        product
                    )


            except Exception:

                continue


        return results