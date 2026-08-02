import json
from pathlib import Path
from dataclasses import asdict


class ProductStorage:


    def __init__(
        self,
        filepath="data/scraping/products.json"
    ):

        self.filepath = Path(
            filepath
        )


    def save(
        self,
        products
    ):

        self.filepath.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        data = [
            asdict(product)
            for product in products
        ]


        with open(
            self.filepath,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )



    def load(self):

        if not self.filepath.exists():

            return []


        with open(
            self.filepath,
            encoding="utf-8"
        ) as file:

            return json.load(file)