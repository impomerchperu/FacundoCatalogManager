from concurrent.futures import ThreadPoolExecutor

import requests


class ImageDownloadManager:
    """
    Gestiona descarga paralela de imágenes.

    Compatible con:

    - dict provenientes de flujos antiguos
    - ScrapedProduct del scraper actual
    """

    def __init__(
        self,
        image_downloader,
        image_validator,
        max_workers=4,
    ):
        self.image_downloader = image_downloader
        self.image_validator = image_validator
        self.max_workers = max_workers

    def download_all(
        self,
        products,
        downloader,
    ):
        results = []

        with ThreadPoolExecutor(
            max_workers=self.max_workers,
        ) as executor:

            futures = [
                executor.submit(
                    self._download_one,
                    product,
                    downloader,
                )
                for product in products
            ]

            for future in futures:
                result = future.result()

                if result:
                    results.append(result)

        return results

    def _download_one(
        self,
        product,
        downloader,
    ):
        code = self._get_value(
            product,
            "code",
        )

        image_url = self._get_image_url(
            product,
        )

        if not code or not image_url:
            return None

        try:
            image_path = self.image_downloader.download(
                code,
                image_url,
                downloader,
            )

            if not self.image_validator.is_valid(
                image_path,
            ):
                return None

        except (
            requests.exceptions.RequestException,
            OSError,
            ValueError,
        ):
            return None

        else:
            self._set_value(
                product,
                "image_path",
                image_path,
            )

            return product

    def _get_value(
        self,
        product,
        field,
    ):
        """
        Obtiene valores desde:

        - dict
        - objetos compatibles
        """

        if isinstance(
            product,
            dict,
        ):
            return product.get(
                field,
            )

        return getattr(
            product,
            field,
            None,
        )

    def _get_image_url(
        self,
        product,
    ):
        """
        Obtiene URL de imagen.

        Mantiene compatibilidad:
        - image
        - image_url
        """

        image = self._get_value(
            product,
            "image",
        )

        if image:
            return image

        return self._get_value(
            product,
            "image_url",
        )

    def _set_value(
        self,
        product,
        field,
        value,
    ):
        """
        Asigna resultado.

        Compatible con:

        - dict
        - dataclass ScrapedProduct
        """

        if isinstance(
            product,
            dict,
        ):
            product[field] = value
            return

        setattr(
            product,
            field,
            value,
        )
