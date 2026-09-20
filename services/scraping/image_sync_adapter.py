from scrapers.sync.image_sync import ImageSync


class ImageSyncAdapter:
    """Adaptador del flujo de scraping al motor de sincronización de imágenes."""

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
