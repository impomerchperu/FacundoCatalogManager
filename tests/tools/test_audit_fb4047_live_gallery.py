from types import SimpleNamespace

from bs4 import BeautifulSoup

import tools.audit_fb4047_live_gallery as audit_module


def test_category_route_resolves_fb4047_before_fetching_detail(monkeypatch):
    card = BeautifulSoup(
        '<div><a href="https://stock.importacionesfacundo.com/'
        'producto/foco-antiestres/">Foco Antiestrés</a></div>',
        "lxml",
    ).div
    product = SimpleNamespace(code="FB-4047", name="Foco Antiestrés")

    class FakeCategoryScraper:
        def __init__(self, *, browser):
            self.browser = browser

    class FakeCollectionScraper:
        instance = None

        def __init__(
            self,
            category_scraper,
            card_extractor,
            product_extractor,
            detail_extractor,
            *,
            max_workers,
            category_page_workers,
        ):
            self.category_scraper = category_scraper
            self.closed = False
            FakeCollectionScraper.instance = self

        def collect_category(self, category_url):
            assert category_url == audit_module.CATEGORY_URL
            return [(card, category_url, product)]

        @staticmethod
        def _card_detail_url(card, page_url, product):
            link = card.select_one('a[href*="/producto/"]')
            return str(link.get("href")) if link is not None else ""

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        audit_module,
        "ResilientCategoryScraper",
        FakeCategoryScraper,
    )
    monkeypatch.setattr(
        audit_module,
        "ProductCollectionScraper",
        FakeCollectionScraper,
    )

    report = {"warnings": []}
    url, collector = audit_module._collect_detail_url_from_category(
        object(),
        report,
    )

    assert url == audit_module.PRODUCT_URL
    assert report["category_page_status"] == "success"
    assert report["category_products_found"] == 1
    assert report["category_target_found"] is True
    assert report["category_match_method"] == "product_code"
    assert collector is FakeCollectionScraper.instance
    assert collector is not None
    assert collector.closed is False
    assert report["warnings"] == []


def test_category_route_failure_falls_back_without_marking_page_valid(monkeypatch):
    class FakeCategoryScraper:
        def __init__(self, *, browser):
            self.browser = browser

    class FakeCollectionScraper:
        def __init__(
            self,
            category_scraper,
            card_extractor,
            product_extractor,
            detail_extractor,
            *,
            max_workers,
            category_page_workers,
        ):
            self.closed = False

        def collect_category(self, category_url):
            raise RuntimeError("category response unavailable")

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        audit_module,
        "ResilientCategoryScraper",
        FakeCategoryScraper,
    )
    monkeypatch.setattr(
        audit_module,
        "ProductCollectionScraper",
        FakeCollectionScraper,
    )

    report = {"warnings": []}
    url, collector = audit_module._collect_detail_url_from_category(
        object(),
        report,
    )

    assert url == audit_module.PRODUCT_URL
    assert report["category_page_status"] == "failed"
    assert report["category_target_found"] is False
    assert report["warnings"] == [
        {
            "stage": "category_scraping",
            "error": "RuntimeError: category response unavailable",
        }
    ]
    assert collector is not None
    assert collector.closed is False


def test_identity_name_prefers_product_title_over_distributor_modal():
    soup = BeautifulSoup(
        """
        <html>
          <body class="single-product">
            <div class="distributor-modal">
              <h2 class="brxe-heading">Acceso Exclusivo para Distribuidores</h2>
            </div>
            <main class="product">
              <div class="summary">
                <h1 class="product_title">Foco Antiestrés</h1>
              </div>
              <div class="woocommerce-product-gallery">
                <img src="https://stock.importacionesfacundo.com/foco.webp">
              </div>
            </main>
          </body>
        </html>
        """,
        "lxml",
    )

    name, source = audit_module._identity_product_name(
        soup,
        "Acceso Exclusivo para Distribuidores",
    )

    assert name == "Foco Antiestrés"
    assert "product_title" in source


def test_identity_name_does_not_mistake_distributor_modal_for_product():
    soup = BeautifulSoup(
        """
        <html>
          <body>
            <div class="distributor-modal">
              <h2 class="brxe-heading">Acceso Exclusivo para Distribuidores</h2>
            </div>
          </body>
        </html>
        """,
        "lxml",
    )

    name, _ = audit_module._identity_product_name(
        soup,
        "Acceso Exclusivo para Distribuidores",
    )

    assert name == "Acceso Exclusivo para Distribuidores"
    assert "foco" not in name.casefold()

