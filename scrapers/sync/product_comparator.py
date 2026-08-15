from services.scraping.product_diff_service import ProductDiffService


class ProductComparator:
    """
    Compara productos scrapeados contra snapshots existentes.

    Clasifica:

    - nuevos
    - actualizados
    - cambios de imagen
    - sin cambios
    - eliminados
    """

    def __init__(
        self,
        diff_service=None,
    ):

        self.diff_service = (
            diff_service
            or ProductDiffService()
        )


    def compare(
        self,
        old_products,
        new_products,
    ):

        old_map = self._build_map(
            old_products
        )

        new_map = self._build_map(
            new_products
        )


        result = {
            "new": [],
            "updated": [],
            "image_changed": [],
            "unchanged": [],
            "removed": [],
        }


        for code, product in new_map.items():

            old = old_map.get(code)


            if old is None:

                result["new"].append(
                    product
                )

                continue


            diff = self.diff_service.compare(
                old,
                product,
            )


            if not diff["changed"]:

                result["unchanged"].append(
                    product
                )

                continue


            if diff.get(
                "image_changed",
                False,
            ) and not diff.get(
                "content_changed",
                False,
            ):

                result["image_changed"].append(
                    product
                )

                continue


            result["updated"].append(
                product
            )


        for code, product in old_map.items():

            if code not in new_map:

                result["removed"].append(
                    product
                )


        return result



    def _build_map(
        self,
        products,
    ):

        result = {}


        for product in products:

            code = self._get(
                product,
                "code",
            )


            if not code:

                continue


            result[code] = product


        return result



    def _get(
        self,
        product,
        field,
    ):

        if isinstance(
            product,
            dict,
        ):

            return product.get(
                field,
                "",
            )


        return getattr(
            product,
            field,
            "",
        )
