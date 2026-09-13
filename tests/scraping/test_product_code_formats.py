from bs4 import BeautifulSoup

import scrapers.collectors  # noqa: F401
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
