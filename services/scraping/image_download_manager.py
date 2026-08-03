from concurrent.futures import ThreadPoolExecutor

import requests


class ImageDownloadManager:
    def __init__(self, image_downloader, image_validator, max_workers=4):

        self.image_downloader = image_downloader
        self.image_validator = image_validator
        self.max_workers = max_workers

    def download_all(self, products, downloader):

        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._download_one, product, downloader)
                for product in products
            ]

            for future in futures:
                result = future.result()

                if result:
                    results.append(result)

        return results

    def _download_one(self, product, downloader):

        code = product.get("code")

        image_url = product.get("image")

        if not code or not image_url:
            return None

        try:
            image_path = self.image_downloader.download(
                code,
                image_url,
                downloader,
            )

            if self.image_validator.is_valid(image_path):
                product["image_path"] = image_path

                return product

        except (
            requests.exceptions.RequestException,
            OSError,
            ValueError,
        ):
            return None

        return None
