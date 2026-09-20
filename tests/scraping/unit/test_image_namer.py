from scrapers.images.image_namer import ImageNamer


def test_image_namer_builds_expected_paths():
    namer = ImageNamer()

    cases = [
        (
            "FB-1812",
            "https://site.com/images/FB-1812.webp",
            "data/images/products/FB-1812.webp",
        ),
        (
            "FB-1800-AZ",
            "https://site.com/a/b/c.png",
            "data/images/products/FB-1800-AZ.png",
        ),
        (
            "ABC123",
            "https://site.com/img/test.jpg",
            "data/images/products/ABC123.jpg",
        ),
        (
            "ABC123",
            "https://site.com/img/test.jpeg",
            "data/images/products/ABC123.jpeg",
        ),
        (
            "ABC123",
            "",
            "data/images/products/ABC123.bin",
        ),
    ]

    for code, url, expected in cases:
        assert namer.build(code, url) == expected
