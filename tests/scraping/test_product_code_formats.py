from bs4 import BeautifulSoup

import scrapers.collectors  # noqa: F401
from scrapers.extractors.code_utils import normalize_code
from scrapers.extractors.product_extractor import ProductExtractor


def test_product_extractor_accepts_letter_only_hyphenated_codes():
    extractor = ProductExtractor()
    cases = {
        "IEV-SFE-CIT": "IEV-SFE-CIT",
        "PPMPLUS-CIT": "PPMPLUS-CIT",
        "IKIOSK-ESTANDAR": "IKIOSK-ESTANDAR",
    }

    for raw_code, expected in cases.items():
        soup = BeautifulSoup(
            f'<span class="sku">{raw_code}</span>',
            "html.parser",
        )
        assert extractor.extract_code(soup) == expected


def test_product_extractor_keeps_numeric_hybrid_codes_supported():
    extractor = ProductExtractor()
    soup = BeautifulSoup('<span class="sku">FB-1800</span>', "html.parser")

    assert extractor.extract_code(soup) == "FB-1800"


def test_product_extractor_accepts_alpha_only_sku_from_explicit_selector():
    soup = BeautifulSoup('<span class="sku">TPSTCB</span>', "html.parser")

    assert ProductExtractor().extract_code(soup) == "TPSTCB"


def test_product_extractor_accepts_alpha_only_sku_from_explicit_json_ld():
    html = '''
    <script type="application/ld+json">
      {"@type":"Product","sku":"TPSTCB"}
    </script>
    '''
    soup = BeautifulSoup(html, "html.parser")

    assert ProductExtractor().extract_code(soup) == "TPSTCB"


def test_alpha_only_code_is_not_accepted_without_explicit_sku_context():
    assert normalize_code("TPSTCB") == ""
    assert ProductExtractor().extract_code(
        BeautifulSoup("<h1>TPSTCB</h1>", "html.parser")
    ) == ""
