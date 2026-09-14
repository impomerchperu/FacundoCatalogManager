from __future__ import annotations

from typing import Any

from .product_collection_scraper import ProductCollectionScraper


class PriceRecoveryProductCollectionScraper(ProductCollectionScraper):
    """Product collector with the validated broad price-recovery policy."""

    @classmethod
    def _missing_price_fields(cls, card: Any, product: Any) -> tuple[str, ...]:
        canonical = super()._missing_price_fields(card, product)
        broad = tuple(
            field
            for field in cls._PRICE_FIELDS
            if float(getattr(product, field, 0.0) or 0.0) <= 0
        )
        return tuple(dict.fromkeys((*canonical, *broad)))

    @classmethod
    def _detail_skip_reason(cls, card: Any, product: Any) -> str | None:
        if cls._missing_price_fields(card, product):
            return None
        return super()._detail_skip_reason(card, product)


__all__ = ["PriceRecoveryProductCollectionScraper"]
