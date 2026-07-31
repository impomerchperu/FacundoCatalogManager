from dataclasses import dataclass


@dataclass
class ScrapedProduct:
    source: str
    url: str

    code: str = ""
    name: str = ""
    category: str = ""

    price: float = 0.0

    image_url: str = ""

    description: str = ""
