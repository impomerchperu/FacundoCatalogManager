from __future__ import annotations

from services.scraping.scraping_config import ScrapingConfig
from services.scraping.scraping_factory import (
    ScrapingFactory as CanonicalScrapingFactory,
)


class ScrapingFactory:
    """Fachada de compatibilidad para la fábrica canónica de scraping."""

    CATALOG_URL = "https://stock.importacionesfacundo.com/tienda/"

    @staticmethod
    def create_runner(
        config: ScrapingConfig | None = None,
    ):
        """Construye el mismo runner utilizado por el flujo actual."""
        return CanonicalScrapingFactory.create_runner(config)
