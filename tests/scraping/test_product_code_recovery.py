from bs4 import BeautifulSoup

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_extractor import ProductExtractor


def test_product_extractor_extracts_explicit_sku_from_detail_markup():
    soup = BeautifulSoup('<span class="sku">FB-1426</span>', "lxml")
    extractor = object.__new__(ProductExtractor)

    assert extractor.extract_code(soup) == "FB-1426"


def test_product_collection_scraper_backfills_authoritative_detail_code():
    product = type("Product", (), {"code": "", "url": ""})()
    detail_product = type("DetailProduct", (), {"code": "FB-7008"})()
    card = BeautifulSoup(
        '<article><a href="/producto/demo/">Demo</a></article>',
        "lxml",
    )
    scraper = object.__new__(ProductCollectionScraper)
    scraper.detail_extractor = object()
    scraper._detail_cache_key = lambda _card, _product, _url: "url:demo"
    scraper._get_detailed_product = lambda _key, _url, _category: detail_product

    result = scraper._enrich_from_detail_page(
        card,
        "https://stock.importacionesfacundo.com/categoria-producto/demo/",
        product,
        "Demo",
    )

    assert result.code == "FB-7008"
    assert result.url == "https://stock.importacionesfacundo.com/producto/demo/"


def test_product_code_normalization_accepts_published_letter_only_skus():
    extractor = CategoryProductExtractor()
    for code in (
        "IEV-SFE-CIT",
        "PPMPLUS-CIT",
        "IKIOSK-ESTANDAR",
    ):
        assert extractor._normalize_code(code) == code


def test_category_product_extractor_accepts_alpha_only_sku_from_card_marker():
    extractor = CategoryProductExtractor()
    soup = BeautifulSoup(
        "<article><h2>Taza Enamel 12 oz</h2><p>SKU: TPSTCB</p></article>",
        "lxml",
    )

    assert extractor._code(soup) == "TPSTCB"


def test_product_collection_scraper_backfills_alpha_only_detail_code():
    product = type("Product", (), {"code": "", "url": "", "description": ""})()
    detail_product = type(
        "DetailProduct",
        (),
        {"code": "TPSTCB", "name": "Taza Enamel 12 oz", "description": ""},
    )()
    card = BeautifulSoup(
        '<article><a href="/producto/taza-enamel-12-oz/">Taza Enamel</a></article>',
        "lxml",
    )
    scraper = object.__new__(ProductCollectionScraper)
    scraper.detail_extractor = object()
    scraper._detail_cache_key = lambda _card, _product, _url: "url:taza-enamel"
    scraper._get_detailed_product = lambda _key, _url, _category: detail_product

    result = scraper._enrich_from_detail_page(
        card,
        "https://stock.importacionesfacundo.com/categoria-producto/insumos-de-sublimacion/",
        product,
        "Insumos de Sublimación",
    )

    assert result.code == "TPSTCB"
    assert result.url == (
        "https://stock.importacionesfacundo.com/producto/taza-enamel-12-oz/"
    )
