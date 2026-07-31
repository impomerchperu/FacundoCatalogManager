class ProductDiffService:

    def compare(self, old, new):

        fields = []

        for field in [
            "name",
            "category",
            "description",
            "price",
            "stock",
            "image_path",
            "image_url",
        ]:

            if old.get(field) != new.get(field):
                fields.append(field)

        return {
            "changed": len(fields) > 0,
            "fields": fields,
        }