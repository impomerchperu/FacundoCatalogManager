from scrapers.sync.image_sync import ImageSync


class ImageSyncAdapter:
    """Adaptador del flujo de scraping al motor de sincronización de imágenes."""

    def __init__(
        self,
        image_sync=None,
        gallery_sync=None,
    ):
        self.image_sync = image_sync or ImageSync()
        self.gallery_sync = gallery_sync

    def sync_products(
        self,
        products,
        progress_callback=None,
    ):
        """
        Procesa imágenes de una colección
        de ScrapedProduct.
        """

        products = self.image_sync.process(products)
        if self.gallery_sync is not None:
            products = self.gallery_sync.sync_products(
                products,
                progress_callback=progress_callback,
            )
        return products
