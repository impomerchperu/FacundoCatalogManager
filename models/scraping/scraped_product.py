from dataclasses import dataclass


@dataclass
class ScrapedProduct:

    source: str = ""
    url: str = ""

    code: str = ""
    name: str = ""
    category: str = ""

    description: str = ""

    stock: int = 0

    price: float = 0.0

    price_sample: float = 0.0
    price_hundred: float = 0.0
    price_thousand: float = 0.0

    image_url: str = ""
    image_path: str = ""

    scraped_at: str = ""


    def __getitem__(self, key):

        return getattr(
            self,
            key
        )