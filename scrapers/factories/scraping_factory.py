from __future__ import annotations

from services.scraping.scraping_config import ScrapingConfig
from services.scraping.scraping_factory import (
    ScrapingFactory as CanonicalScrapingFactory,
)


class ScrapingFactory:
    """Fachada de compatibilidad para la fábrica canónica de scraping."""

    @staticmethod
    def create_runner(config: ScrapingConfig | None = None):
        """Expone la API moderna delegando en la fábrica canónica."""
        return CanonicalScrapingFactory.create_runner(config)

    @staticmethod
    def create():
        """Mantiene la API histórica y devuelve el runner canónico."""
        return CanonicalScrapingFactory.create_runner()
