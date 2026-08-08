from dataclasses import asdict


class ProductComparator:
    def compare(
        self,
        old_products,
        new_products,
    ):

        old_map = {}

        for product in old_products:

            data = self._to_dict(product)

            code = data.get("code")

            if code:
                old_map[code] = data


        result = {
            "new": [],
            "updated": [],
            "unchanged": [],
        }


        for product in new_products:

            code = getattr(
                product,
                "code",
                None,
            )

            if code not in old_map:

                result["new"].append(product)

                continue


            old = old_map[code]


            if self._changed(
                old,
                product,
            ):

                result["updated"].append(product)

            else:

                result["unchanged"].append(product)


        return result


    def _to_dict(
        self,
        product,
    ):

        if isinstance(product, dict):
            return product


        try:
            return asdict(product)

        except TypeError:
            return product.__dict__


    def _changed(
        self,
        old,
        new,
    ):

        fields = [
            "name",
            "description",
            "stock",
            "price_sample",
            "price_hundred",
            "price_thousand",
            "image_url",
            "image_hash",
            "image_error",
        ]


        for field in fields:

            old_value = old.get(field)

            new_value = getattr(
                new,
                field,
                None,
            )

            if old_value != new_value:
                return True


        return False
