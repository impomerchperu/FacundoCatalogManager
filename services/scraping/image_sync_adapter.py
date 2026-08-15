from scrapers.sync.image_sync import ImageSync


class ImageSyncAdapter:
    """
    Adaptador entre FullScrapingService
    y el motor moderno ImageSync.
    """

    def __init__(
        self,
        image_sync=None,
    ):
        self.image_sync = (
            image_sync
            or ImageSync()
        )

    def sync_products(
        self,
        products,
    ):
        """
        Procesa imágenes de una colección
        de ScrapedProduct.
        """

        return self.image_sync.process(
            products,
        )
