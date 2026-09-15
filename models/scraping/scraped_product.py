from dataclasses import dataclass, field
from datetime import datetime, timezone


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

    color_stock: dict[str, int] = field(default_factory=dict)

    image_url: str = ""
    image_path: str = ""

    image_hash: str = ""

    content_hash: str = ""

    image_error: str = ""

    scraped_at: str = ""

    updated_at: str = ""

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if name != "price_sample":
            return
        try:
            sample_price = float(value or 0.0)
            current_price = float(getattr(self, "price", 0.0) or 0.0)
        except (TypeError, ValueError):
            return
        if current_price <= 0.0 and sample_price > 0.0:
            object.__setattr__(self, "price", sample_price)

    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()

        self.color_stock = {
            str(color).strip(): max(int(stock), 0)
            for color, stock in self.color_stock.items()
            if str(color).strip()
        }

    def __getitem__(self, key):
        return getattr(self, key)
