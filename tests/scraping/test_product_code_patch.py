from types import SimpleNamespace

from scrapers.collectors import product_code_patch
from scrapers.extractors.product_extractor import ProductExtractor


def test_product_code_patch_extracts_explicit_sku_from_detail_markup():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup('<span class="sku">FB-1426</span>', "lxml")
    extractor = object.__new__(ProductExtractor)
    extractor._legacy_extract_code = lambda _soup: ""

    assert product_code_patch._extract_code(extractor, soup) == "FB-1426"


def test_product_code_patch_backfills_authoritative_detail_code(monkeypatch):
    product = SimpleNamespace(
        code="",
        url="https://stock.importacionesfacundo.com/producto/demo/",
    )
    detail_product = SimpleNamespace(code="FB-7008")
    card = SimpleNamespace()
    scraper = object.__new__(product_code_patch.ProductCollectionScraper)
    scraper.detail_extractor = object()
    scraper._card_detail_url = lambda _card, _page, _product: (
        "https://stock.importacionesfacundo.com/producto/demo/"
    )
    scraper._detail_cache_key = lambda _card, _product, url: f"url:{url}"
    scraper._get_detailed_product = lambda _key, _url, _category: detail_product

    monkeypatch.setattr(
        product_code_patch,
        "_ORIGINAL_ENRICH_FROM_DETAIL_PAGE",
        lambda _self, _card, _page, current, _category: current,
    )

    result = product_code_patch._enrich_with_authoritative_code(
        scraper,
        card,
        "https://stock.importacionesfacundo.com/categoria-producto/demo/",
        product,
        "Demo",
    )

    assert result.code == "FB-7008"
    assert result.url == "https://stock.importacionesfacundo.com/producto/demo/"
