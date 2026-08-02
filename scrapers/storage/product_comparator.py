class ProductComparator:


    def compare(
        self,
        old_products,
        new_products
    ):

        old_map = {
            p["code"]: p
            for p in old_products
            if p.get("code")
        }


        result = {

            "new": [],

            "updated": [],

            "unchanged": []

        }


        for product in new_products:

            code = product.code


            if code not in old_map:

                result["new"].append(
                    product
                )

                continue



            old = old_map[code]


            if self._changed(
                old,
                product
            ):

                result["updated"].append(
                    product
                )

            else:

                result["unchanged"].append(
                    product
                )


        return result



    def _changed(
        self,
        old,
        new
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

            "image_error"

        ]


        for field in fields:


            old_value = old.get(
                field
            )


            new_value = getattr(
                new,
                field,
                None
            )


            if old_value != new_value:

                return True



        return False