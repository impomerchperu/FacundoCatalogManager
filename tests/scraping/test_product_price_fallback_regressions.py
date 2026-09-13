from scrapers.extractors.price_extractor import PriceExtractor


def test_price_extractor_distinguishes_decimal_comma_from_thousands_comma():
    extractor = PriceExtractor()

    assert extractor._parse_price("8,50") == 8.5
    assert extractor._parse_price("1,250") == 1250.0
    assert extractor._parse_price("12,500") == 12500.0
    assert extractor._parse_price("1,250,000") == 1250000.0
