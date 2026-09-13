from types import SimpleNamespace

from services.scraping.scraping_session import ScrapingSession


def test_scraping_session_skips_catalog_persistence_when_sync_service_owns_it():
    saved = []

    class Repository:
        def save(self, product):
            saved.append(product)

    runner = SimpleNamespace(
        scraping_service=SimpleNamespace(
            catalog_sync_service=object(),
        )
    )
    session = ScrapingSession(runner, catalog_repository=Repository())
    session.result.products = [object(), object()]

    session._persist_catalog_products()

    assert saved == []


def test_scraping_session_persists_when_no_catalog_sync_service_exists():
    saved = []

    class Repository:
        def save(self, product):
            saved.append(product)

    products = [object(), object()]
    runner = SimpleNamespace(
        scraping_service=SimpleNamespace(
            catalog_sync_service=None,
        )
    )
    session = ScrapingSession(runner, catalog_repository=Repository())
    session.result.products = products

    session._persist_catalog_products()

    assert saved == products
