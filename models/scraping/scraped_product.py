from dataclasses import dataclass
from datetime import datetime


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

    image_hash: str = ""
    image_error: str = ""

    scraped_at: str = ""

    updated_at: str = ""


    def __post_init__(self):

        if not self.scraped_at:

            self.scraped_at = (
                datetime.now()
                .isoformat()
            )


    def __getitem__(self, key):

        return getattr(
            self,
            key
        )