from scrapers.images.image_manager import ImageManager


class ImageSync:
    """
    Gestiona la sincronización incremental
    de imágenes de productos.

    Compatible con:
    - sincronización individual
    - procesamiento masivo
    """


    def __init__(
        self,
        image_manager=None,
    ):

        self.image_manager = (
            image_manager
            or ImageManager()
        )


    # =====================================================
    # API COMPATIBILIDAD TESTS / LEGACY
    # =====================================================

    def synchronize(
        self,
        product,
        old_product=None,
    ):
        """
        Sincroniza un único producto.

        Devuelve dict para mantener compatibilidad
        con pruebas antiguas.
        """

        result = self.sync_product(
            product,
            old_product,
        )


        return {
            "image_path": getattr(
                result,
                "image_path",
                ""
            ),

            "image_hash": getattr(
                result,
                "image_hash",
                ""
            ),
        }



    # =====================================================
    # PROCESAMIENTO MASIVO
    # =====================================================

    def process(
        self,
        products,
    ):

        processed = []


        for product in products:

            processed.append(
                self.sync_product(
                    product
                )
            )


        return processed



    # =====================================================
    # PRODUCTO INDIVIDUAL
    # =====================================================

    def sync_product(
        self,
        product,
        old_product=None,
    ):

        if not product.image_url:

            return product



        # ---------------------------------
        # PRODUCTO EXISTENTE
        # ---------------------------------

        if old_product:


            old_path = (
                old_product.get(
                    "image_path",
                    ""
                )
            )


            old_hash = (
                old_product.get(
                    "image_hash",
                    ""
                )
            )


            if (
                old_path
                and old_hash
            ):

                product.image_path = old_path

                product.image_hash = old_hash

                return product



        # ---------------------------------
        # NUEVA IMAGEN
        # ---------------------------------

        image_data = self.image_manager.process(
            product.code,
            product.image_url,
        )


        product.image_path = (
            image_data.get(
                "image_path",
                ""
            )
        )


        product.image_hash = (
            image_data.get(
                "image_hash",
                ""
            )
        )


        return product