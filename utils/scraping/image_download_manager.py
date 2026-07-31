from concurrent.futures import ThreadPoolExecutor


class ImageDownloadManager:

    def __init__(
        self,
        image_downloader,
        max_workers=5
    ):

        self.image_downloader = image_downloader
        self.max_workers = max_workers


    def download_all(
        self,
        products,
        downloader
    ):

        results = []


        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            futures = []


            for product in products:

                future = executor.submit(
                    self.image_downloader.download,
                    product["code"],
                    product["image"],
                    downloader
                )

                futures.append(
                    future
                )


            for future in futures:

                results.append(
                    future.result()
                )


        return results